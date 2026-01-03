"""Confidence scoring service for answer quality assessment."""

from typing import Optional

import openai
from loguru import logger


class ConfidenceScorer:
    """Service for computing answer confidence scores."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        min_threshold: float = 0.5,
    ) -> None:
        """Initialize confidence scorer."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.min_threshold = min_threshold
        logger.info(f"Initialized ConfidenceScorer with threshold: {min_threshold}")

    async def compute_confidence(
        self,
        query: str,
        answer: str,
        context: str,
        retrieved_chunks: list[str],
        consistency_score: Optional[float] = None,
    ) -> dict:
        """Compute comprehensive confidence score for an answer."""
        
        # Component 1: Context coverage score
        coverage_score = await self._compute_context_coverage(query, retrieved_chunks)
        
        # Component 2: Answer completeness score
        completeness_score = await self._compute_answer_completeness(query, answer, context)
        
        # Component 3: Context relevance score
        relevance_score = await self._compute_context_relevance(query, context)
        
        # Component 4: Use consistency score if available
        if consistency_score is None:
            consistency_score = 0.7  # Default
        
        # Weighted combination
        weights = {
            'coverage': 0.25,
            'completeness': 0.25,
            'relevance': 0.25,
            'consistency': 0.25,
        }
        
        overall_confidence = (
            coverage_score * weights['coverage'] +
            completeness_score * weights['completeness'] +
            relevance_score * weights['relevance'] +
            consistency_score * weights['consistency']
        )
        
        # Determine if we should say "I don't know"
        should_abstain = overall_confidence < self.min_threshold
        
        confidence_data = {
            'overall_confidence': overall_confidence,
            'coverage_score': coverage_score,
            'completeness_score': completeness_score,
            'relevance_score': relevance_score,
            'consistency_score': consistency_score,
            'should_abstain': should_abstain,
            'confidence_level': self._get_confidence_level(overall_confidence),
        }
        
        logger.info(f"Confidence: {overall_confidence:.3f} ({confidence_data['confidence_level']})")
        return confidence_data

    async def _compute_context_coverage(
        self,
        query: str,
        retrieved_chunks: list[str],
    ) -> float:
        """Assess if retrieved context contains information to answer the query."""
        if not retrieved_chunks:
            return 0.0
        
        try:
            context_sample = "\n".join([chunk[:150] for chunk in retrieved_chunks[:5]])
            
            prompt = f"""Does the retrieved context contain sufficient information to answer this query?

Query: {query}

Context (sample):
{context_sample}

Rate the coverage from 0.0 to 1.0:
- 1.0: Complete information available
- 0.7-0.9: Most information available
- 0.4-0.6: Partial information
- 0.0-0.3: Insufficient information

Respond with ONLY a number."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert evaluator. Respond with only a number."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=10,
            )

            score = float(response.choices[0].message.content.strip())
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.warning(f"Coverage computation failed: {e}")
            return 0.5

    async def _compute_answer_completeness(
        self,
        query: str,
        answer: str,
        context: str,
    ) -> float:
        """Assess if the answer fully addresses the query."""
        try:
            prompt = f"""Rate how completely this answer addresses the query (0.0 to 1.0).

Query: {query}

Answer: {answer}

Consider:
- Does it address all parts of the question?
- Is it specific enough?
- Does it hedge unnecessarily?

Respond with ONLY a number."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert evaluator. Respond with only a number."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=10,
            )

            score = float(response.choices[0].message.content.strip())
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.warning(f"Completeness computation failed: {e}")
            return 0.6

    async def _compute_context_relevance(
        self,
        query: str,
        context: str,
    ) -> float:
        """Assess relevance of context to the query."""
        try:
            context_sample = context[:500]
            
            prompt = f"""Rate how relevant this context is to answering the query (0.0 to 1.0).

Query: {query}

Context (sample):
{context_sample}

Respond with ONLY a number."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert evaluator. Respond with only a number."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=10,
            )

            score = float(response.choices[0].message.content.strip())
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.warning(f"Relevance computation failed: {e}")
            return 0.6

    def _get_confidence_level(self, score: float) -> str:
        """Convert numeric score to confidence level."""
        if score >= 0.8:
            return "HIGH"
        elif score >= 0.6:
            return "MEDIUM"
        elif score >= 0.4:
            return "LOW"
        else:
            return "VERY_LOW"

    def should_use_answer(self, confidence_data: dict) -> bool:
        """Determine if answer is confident enough to return."""
        return not confidence_data['should_abstain']

    def get_low_confidence_response(self, query: str, confidence_data: dict) -> str:
        """Generate appropriate response for low-confidence scenarios."""
        confidence = confidence_data['overall_confidence']
        
        if confidence < 0.3:
            return "I don't have enough information in my knowledge base to answer this question accurately."
        elif confidence < 0.5:
            return "I found some relevant information but cannot provide a confident answer. The available context may be incomplete or insufficient for this question."
        else:
            return "I have limited confidence in my answer due to incomplete information."
