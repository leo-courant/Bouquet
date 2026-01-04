"""Citation validator for post-generation verification."""

import re
from typing import Optional

import openai
from loguru import logger

from app.domain import SearchResult


class CitationValidator:
    """Service for validating citations in generated answers."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
    ) -> None:
        """Initialize citation validator."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        logger.info("Initialized CitationValidator")

    async def validate_answer_citations(
        self,
        answer: str,
        sources: list[SearchResult],
    ) -> dict:
        """
        Validate that all citations in answer actually support the claims.
        
        Args:
            answer: Generated answer with [Source N] citations
            sources: List of sources that were provided for answer generation
            
        Returns:
            Validation results with issues and score
        """
        
        # Extract all citations from answer
        citations = self._extract_citations(answer)
        
        if not citations:
            logger.warning("No citations found in answer")
            return {
                'valid': False,
                'score': 0.0,
                'issues': ['No citations found in answer'],
                'total_citations': 0,
                'validated_citations': 0,
            }
        
        # Extract claims associated with each citation
        claims_by_citation = self._extract_claims_with_citations(answer)
        
        # Validate each citation
        validation_results = []
        
        for citation_num, claims in claims_by_citation.items():
            # Get the source
            source_idx = citation_num - 1  # Citations are 1-indexed
            
            if source_idx >= len(sources):
                validation_results.append({
                    'citation': citation_num,
                    'valid': False,
                    'issue': f'Citation [Source {citation_num}] references non-existent source',
                })
                continue
            
            source = sources[source_idx]
            
            # Validate each claim against this source
            for claim in claims:
                is_valid = await self._validate_claim_against_source(
                    claim, source.content
                )
                
                validation_results.append({
                    'citation': citation_num,
                    'claim': claim,
                    'valid': is_valid,
                    'source_preview': source.content[:150],
                })
        
        # Calculate overall validation score
        valid_count = sum(1 for r in validation_results if r['valid'])
        total_count = len(validation_results)
        
        # Ensure non-negative values
        valid_count = max(0, valid_count)
        total_count = max(0, total_count)
        
        validation_score = valid_count / total_count if total_count > 0 else 0.0
        # Clamp score to valid range [0.0, 1.0]
        validation_score = max(0.0, min(1.0, validation_score))
        
        # Collect issues
        issues = [
            f"Citation {r['citation']}: {r.get('issue', 'Claim not supported by source')}"
            for r in validation_results if not r['valid']
        ]
        
        result = {
            'valid': validation_score >= 0.8 and total_count > 0,  # 80% threshold and at least one claim
            'score': validation_score,
            'total_citations': len(citations),
            'validated_citations': valid_count,
            'total_claims': total_count,
            'issues': issues,
            'details': validation_results,
        }
        
        if not result['valid']:
            logger.warning(
                f"Citation validation failed: {validation_score:.2%} "
                f"({valid_count}/{total_count} claims valid)"
            )
        else:
            logger.info(
                f"Citation validation passed: {validation_score:.2%}"
            )
        
        return result

    def _extract_citations(self, answer: str) -> list[int]:
        """Extract all [Source N] citations from answer."""
        
        pattern = r'\[Source (\d+)\]'
        matches = re.findall(pattern, answer)
        
        citations = sorted(set(int(m) for m in matches))
        
        logger.debug(f"Found {len(citations)} unique citations in answer")
        
        return citations

    def _extract_claims_with_citations(self, answer: str) -> dict[int, list[str]]:
        """
        Extract claims and their associated citations.
        
        Returns dict mapping citation number to list of claims it supports.
        """
        
        claims_by_citation = {}
        
        # Split answer into sentences
        sentences = re.split(r'[.!?]+', answer)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Find citations in this sentence
            citations = re.findall(r'\[Source (\d+)\]', sentence)
            
            if citations:
                # Remove citation markers to get the claim
                claim = re.sub(r'\[Source \d+\]', '', sentence).strip()
                
                if claim:
                    for citation_str in citations:
                        citation_num = int(citation_str)
                        
                        if citation_num not in claims_by_citation:
                            claims_by_citation[citation_num] = []
                        
                        claims_by_citation[citation_num].append(claim)
        
        logger.debug(
            f"Extracted claims for {len(claims_by_citation)} citations"
        )
        
        return claims_by_citation

    async def _validate_claim_against_source(
        self,
        claim: str,
        source_content: str,
    ) -> bool:
        """
        Validate that a specific claim is supported by source content.
        
        Uses LLM to check if claim is entailed by source.
        """
        
        prompt = f"""Does the following source text support or entail this claim?

CLAIM: {claim}

SOURCE: {source_content[:500]}

Answer YES if the source clearly supports the claim.
Answer NO if the source contradicts or doesn't support the claim.
Answer PARTIAL if the source partially supports it but lacks full support.

Consider:
- Direct statements that match the claim
- Logical entailment (claim follows from source)
- Paraphrasing (same meaning, different words)

Do NOT accept if:
- Source lacks the information
- Claim makes unsupported leaps
- Claim contradicts source

Answer (YES/NO/PARTIAL):"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at validating factual claims against sources."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=100,
            )

            result = response.choices[0].message.content.strip().upper()
            
            # Accept YES or PARTIAL as valid
            is_valid = 'YES' in result or 'PARTIAL' in result
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Failed to validate claim: {e}")
            # Default to valid to avoid false negatives on errors
            return True

    async def suggest_citation_fixes(
        self,
        answer: str,
        sources: list[SearchResult],
        validation_result: dict,
    ) -> Optional[str]:
        """
        Suggest corrections for invalid citations.
        
        Returns corrected answer or None if no fixes needed.
        """
        
        if validation_result['valid']:
            return None  # No fixes needed
        
        if not validation_result['issues']:
            return None
        
        # Build correction prompt
        issues_text = "\n".join(f"- {issue}" for issue in validation_result['issues'])
        
        sources_text = "\n\n".join(
            f"[Source {i+1}]\n{src.content[:300]}"
            for i, src in enumerate(sources[:5])
        )
        
        prompt = f"""The following answer has citation issues. Please correct the citations or remove unsupported claims.

ORIGINAL ANSWER:
{answer}

SOURCES:
{sources_text}

ISSUES FOUND:
{issues_text}

Provide a CORRECTED version of the answer where:
1. All citations properly support their claims
2. Unsupported claims are removed or rephrased
3. Citations remain in [Source N] format
4. The answer maintains its core message

CORRECTED ANSWER:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You fix citation errors while preserving answer quality."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=1000,
            )

            corrected = response.choices[0].message.content.strip()
            
            logger.info("Generated citation corrections")
            
            return corrected
            
        except Exception as e:
            logger.error(f"Failed to suggest fixes: {e}")
            return None

    async def validate_citation_coverage(
        self,
        answer: str,
        sources: list[SearchResult],
    ) -> dict:
        """
        Check if all important claims in answer have citations.
        
        Identifies claims that should have citations but don't.
        """
        
        # Extract sentences without citations
        sentences = re.split(r'[.!?]+', answer)
        
        uncited_claims = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if sentence has citation
            has_citation = bool(re.search(r'\[Source \d+\]', sentence))
            
            if not has_citation:
                # Check if it's a factual claim (not a meta-statement)
                if await self._is_factual_claim(sentence):
                    uncited_claims.append(sentence)
        
        coverage_score = 1.0 - (len(uncited_claims) / max(len(sentences), 1))
        
        return {
            'has_full_coverage': len(uncited_claims) == 0,
            'coverage_score': coverage_score,
            'uncited_claims': uncited_claims,
            'total_sentences': len(sentences),
        }

    async def _is_factual_claim(self, sentence: str) -> bool:
        """
        Determine if sentence makes a factual claim requiring citation.
        
        Meta-statements like "I don't have information..." don't need citations.
        """
        
        # Quick heuristic checks first
        meta_phrases = [
            "i don't have",
            "i couldn't find",
            "based on the",
            "according to",
            "in summary",
            "to summarize",
            "in conclusion",
        ]
        
        sentence_lower = sentence.lower()
        
        if any(phrase in sentence_lower for phrase in meta_phrases):
            return False
        
        # Check if it's a question
        if sentence.strip().endswith('?'):
            return False
        
        # If it mentions specific facts, numbers, names, it likely needs citation
        has_factual_indicators = bool(re.search(r'\b\d+\b', sentence))  # Numbers
        has_proper_nouns = bool(re.search(r'\b[A-Z][a-z]+\b', sentence))  # Capitalized words
        
        # Short sentences without facts probably don't need citations
        if len(sentence.split()) < 5 and not (has_factual_indicators or has_proper_nouns):
            return False
        
        return True  # Default to requiring citation

    async def batch_validate_citations(
        self,
        answers_with_sources: list[tuple[str, list[SearchResult]]],
    ) -> list[dict]:
        """
        Validate citations for multiple answers in batch.
        
        More efficient for processing multiple answers.
        """
        
        results = []
        
        for answer, sources in answers_with_sources:
            validation = await self.validate_answer_citations(answer, sources)
            results.append(validation)
        
        # Summary statistics
        total_valid = sum(1 for r in results if r['valid'])
        avg_score = sum(r['score'] for r in results) / len(results) if results else 0.0
        
        logger.info(
            f"Batch validation: {total_valid}/{len(results)} valid, "
            f"avg score: {avg_score:.2%}"
        )
        
        return results
