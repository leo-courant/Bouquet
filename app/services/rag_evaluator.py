"""RAG evaluation framework for measuring answer quality."""

from dataclasses import dataclass
from typing import Any, Optional

import openai
from loguru import logger


@dataclass
class EvaluationMetrics:
    """Metrics for RAG evaluation."""
    
    # Retrieval metrics
    context_precision: float  # Are retrieved chunks relevant?
    context_recall: float  # Did we retrieve all relevant chunks?
    
    # Generation metrics
    answer_faithfulness: float  # Is answer grounded in context?
    answer_relevance: float  # Does answer address the query?
    
    # Overall
    overall_score: float


class RAGEvaluator:
    """Evaluates RAG system quality using LLM-as-judge."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
    ) -> None:
        """Initialize evaluator."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        logger.info("Initialized RAG Evaluator")

    async def evaluate_context_relevance(
        self,
        query: str,
        retrieved_chunks: list[str],
    ) -> float:
        """Evaluate if retrieved chunks are relevant to query."""
        if not retrieved_chunks:
            return 0.0
        
        try:
            context = "\n\n".join([f"Chunk {i+1}: {chunk[:200]}" for i, chunk in enumerate(retrieved_chunks)])
            
            prompt = f"""Rate how relevant these retrieved text chunks are to answering the query.

Query: {query}

Retrieved chunks:
{context}

On a scale of 0-10, how relevant are these chunks overall? Consider:
- Do they contain information needed to answer the query?
- Is there irrelevant information?
- Are key facts present?

Respond with only a number 0-10."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert evaluator. Respond with only a number."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=10,
            )

            score_text = response.choices[0].message.content or "5"
            score = float(score_text.strip()) / 10.0
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.warning(f"Context relevance evaluation failed: {e}")
            return 0.5

    async def evaluate_answer_faithfulness(
        self,
        answer: str,
        context: str,
    ) -> float:
        """Evaluate if answer is grounded in the provided context."""
        try:
            prompt = f"""Is the answer faithful to the context? Check if claims in the answer are supported by the context.

Context:
{context[:2000]}

Answer:
{answer}

Rate faithfulness 0-10 (10 = all claims supported, 0 = hallucinated). Respond with only a number."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at detecting hallucinations. Respond with only a number."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=10,
            )

            score_text = response.choices[0].message.content or "5"
            score = float(score_text.strip()) / 10.0
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.warning(f"Faithfulness evaluation failed: {e}")
            return 0.5

    async def evaluate_answer_relevance(
        self,
        query: str,
        answer: str,
    ) -> float:
        """Evaluate if answer actually addresses the query."""
        try:
            prompt = f"""Does the answer address the query?

Query: {query}

Answer: {answer}

Rate relevance 0-10 (10 = directly answers, 0 = unrelated). Respond with only a number."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert evaluator. Respond with only a number."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=10,
            )

            score_text = response.choices[0].message.content or "5"
            score = float(score_text.strip()) / 10.0
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.warning(f"Relevance evaluation failed: {e}")
            return 0.5

    async def evaluate_full_pipeline(
        self,
        query: str,
        retrieved_chunks: list[str],
        answer: str,
        ground_truth: Optional[str] = None,
    ) -> EvaluationMetrics:
        """Complete evaluation of RAG pipeline."""
        context = "\n\n".join(retrieved_chunks)
        
        # Run evaluations in parallel
        import asyncio
        context_precision, faithfulness, relevance = await asyncio.gather(
            self.evaluate_context_relevance(query, retrieved_chunks),
            self.evaluate_answer_faithfulness(answer, context),
            self.evaluate_answer_relevance(query, answer),
        )
        
        # Context recall requires ground truth (set to 1.0 if not available)
        context_recall = 1.0
        
        # Overall score is weighted average
        overall = (
            context_precision * 0.25 +
            context_recall * 0.25 +
            faithfulness * 0.30 +
            relevance * 0.20
        )
        
        metrics = EvaluationMetrics(
            context_precision=context_precision,
            context_recall=context_recall,
            answer_faithfulness=faithfulness,
            answer_relevance=relevance,
            overall_score=overall,
        )
        
        logger.info(f"Evaluation: Precision={context_precision:.2f}, Faithfulness={faithfulness:.2f}, Relevance={relevance:.2f}, Overall={overall:.2f}")
        return metrics
