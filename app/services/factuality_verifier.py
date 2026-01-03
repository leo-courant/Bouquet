"""Factuality verification service for detecting hallucinations."""

import re
from typing import Optional

import openai
from loguru import logger


class FactualityVerifier:
    """Service for verifying factual accuracy and detecting hallucinations."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
    ) -> None:
        """Initialize factuality verifier."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        logger.info("Initialized FactualityVerifier")

    async def verify_answer_factuality(
        self,
        answer: str,
        context: str,
    ) -> dict:
        """Comprehensive factuality verification."""
        
        # Extract claims from answer
        claims = await self._extract_claims(answer)
        
        # Verify each claim
        verified_claims = []
        unverified_claims = []
        
        for claim in claims:
            is_supported = await self._verify_claim_against_context(claim, context)
            
            if is_supported:
                verified_claims.append(claim)
            else:
                unverified_claims.append(claim)
        
        # Check for contradictions
        contradictions = await self._detect_contradictions(context)
        
        # Compute overall factuality score
        total_claims = len(claims)
        if total_claims == 0:
            factuality_score = 1.0
        else:
            factuality_score = len(verified_claims) / total_claims
        
        result = {
            'factuality_score': factuality_score,
            'total_claims': total_claims,
            'verified_claims': len(verified_claims),
            'unverified_claims': unverified_claims,
            'contradictions_detected': len(contradictions) > 0,
            'contradictions': contradictions,
            'is_factual': factuality_score >= 0.8 and len(contradictions) == 0,
        }
        
        logger.info(f"Factuality score: {factuality_score:.3f} ({len(verified_claims)}/{total_claims} claims verified)")
        return result

    async def _extract_claims(self, answer: str) -> list[str]:
        """Extract individual factual claims from answer."""
        try:
            prompt = f"""Extract all factual claims from this answer. Each claim should be a specific, verifiable statement.

Answer: {answer}

Instructions:
- List each distinct factual claim
- One claim per line
- Be specific and atomic
- Skip opinions or hedging phrases

Example:
- The sky is blue
- Water boils at 100°C
- Python was created in 1991"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at breaking down text into factual claims."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=300,
            )

            result = response.choices[0].message.content.strip()
            
            # Parse claims
            claims = []
            for line in result.split('\n'):
                line = line.strip()
                # Remove bullet points, numbers, etc.
                line = re.sub(r'^[-•*\d.)\]]+\s*', '', line)
                if line and len(line) > 10:
                    claims.append(line)
            
            return claims

        except Exception as e:
            logger.warning(f"Claim extraction failed: {e}")
            # Fallback: split by sentences
            return [s.strip() for s in answer.split('.') if len(s.strip()) > 10]

    async def _verify_claim_against_context(
        self,
        claim: str,
        context: str,
    ) -> bool:
        """Verify if a specific claim is supported by context."""
        try:
            prompt = f"""Is this claim supported by the context?

CLAIM: {claim}

CONTEXT:
{context[:1500]}

Respond with ONLY:
- "YES" if the claim is clearly supported by the context
- "NO" if the claim is not supported or contradicted
- "PARTIAL" if partially supported"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a strict fact-checker. Be conservative - only say YES if clearly supported."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=10,
            )

            result = response.choices[0].message.content.strip().upper()
            return result in ["YES", "PARTIAL"]

        except Exception as e:
            logger.warning(f"Claim verification failed: {e}")
            return True  # Assume valid on error

    async def _detect_contradictions(self, context: str) -> list[dict]:
        """Detect contradictions within the context."""
        try:
            # Sample context if too long
            context_sample = context[:2000]
            
            prompt = f"""Analyze this context for contradictions or conflicting information.

Context:
{context_sample}

If you find contradictions, list them in this format:
CONTRADICTION: [brief description]
Statement 1: [first conflicting statement]
Statement 2: [second conflicting statement]

If no contradictions found, respond with: NONE"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at detecting logical contradictions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=300,
            )

            result = response.choices[0].message.content.strip()
            
            if result == "NONE":
                return []
            
            # Parse contradictions
            contradictions = []
            blocks = result.split('CONTRADICTION:')
            
            for block in blocks[1:]:  # Skip first empty block
                lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
                if len(lines) >= 3:
                    contradictions.append({
                        'description': lines[0],
                        'statement1': lines[1].replace('Statement 1:', '').strip(),
                        'statement2': lines[2].replace('Statement 2:', '').strip(),
                    })
            
            return contradictions

        except Exception as e:
            logger.warning(f"Contradiction detection failed: {e}")
            return []

    async def verify_numerical_fact(
        self,
        claim: str,
        context: str,
    ) -> tuple[bool, Optional[str]]:
        """Specifically verify numerical facts (dates, numbers, etc.)."""
        # Extract numbers from claim
        numbers_in_claim = re.findall(r'\b\d+(?:\.\d+)?\b', claim)
        
        if not numbers_in_claim:
            return True, None  # No numbers to verify
        
        # Check if these numbers appear in context
        numbers_in_context = re.findall(r'\b\d+(?:\.\d+)?\b', context)
        
        # Simple verification: all numbers in claim should be in context
        for num in numbers_in_claim:
            if num not in numbers_in_context:
                return False, f"Number '{num}' in claim not found in context"
        
        return True, None

    async def suggest_corrections(
        self,
        answer: str,
        factuality_result: dict,
        context: str,
    ) -> Optional[str]:
        """Suggest corrections for factually incorrect answer."""
        
        if factuality_result['is_factual']:
            return None
        
        if not factuality_result['unverified_claims']:
            return None
        
        try:
            unverified = "\n".join(factuality_result['unverified_claims'])
            
            prompt = f"""This answer contains unverified claims. Provide a corrected version that only includes information from the context.

Original Answer:
{answer}

Unverified Claims:
{unverified}

Context:
{context[:1500]}

Provide a corrected answer that:
1. Removes or rephrases unverified claims
2. Only makes claims supported by the context
3. Maintains the same helpful tone
4. Says "I don't know" if information is insufficient"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert editor focused on factual accuracy."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=400,
            )

            corrected = response.choices[0].message.content.strip()
            logger.info("Generated corrected answer")
            return corrected

        except Exception as e:
            logger.error(f"Failed to suggest corrections: {e}")
            return None
