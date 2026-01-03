"""Self-consistency service for answer verification."""

from collections import Counter
from typing import Optional

import openai
from loguru import logger


class SelfConsistencyService:
    """Service for generating and verifying multiple answer candidates."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        num_samples: int = 3,
    ) -> None:
        """Initialize self-consistency service."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.num_samples = num_samples
        logger.info(f"Initialized SelfConsistencyService with {num_samples} samples")

    async def generate_multiple_answers(
        self,
        query: str,
        context: str,
        system_prompt: str,
    ) -> list[str]:
        """Generate multiple answer candidates with varied temperature."""
        answers = []
        
        # Generate with different temperatures for diversity
        temperatures = [0.3, 0.5, 0.7][:self.num_samples]
        
        for i, temp in enumerate(temperatures):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"},
                    ],
                    temperature=temp,
                    max_tokens=500,
                )
                
                answer = response.choices[0].message.content.strip()
                answers.append(answer)
                logger.debug(f"Generated answer {i+1}/{self.num_samples} (temp={temp})")
                
            except Exception as e:
                logger.warning(f"Failed to generate answer {i+1}: {e}")
                continue
        
        return answers

    async def select_most_consistent(
        self,
        query: str,
        answers: list[str],
    ) -> tuple[str, float]:
        """Select the most consistent answer using LLM-based similarity."""
        if not answers:
            return "I couldn't generate a reliable answer.", 0.0
        
        if len(answers) == 1:
            return answers[0], 0.5
        
        # Use LLM to compute pairwise semantic similarity
        similarity_matrix = []
        
        for i, ans1 in enumerate(answers):
            row = []
            for j, ans2 in enumerate(answers):
                if i == j:
                    row.append(1.0)
                elif i > j:
                    # Use cached value
                    row.append(similarity_matrix[j][i])
                else:
                    # Compute similarity
                    sim = await self._compute_similarity(ans1, ans2)
                    row.append(sim)
            similarity_matrix.append(row)
        
        # Select answer with highest average similarity to others
        avg_similarities = [
            sum(row) / len(row) for row in similarity_matrix
        ]
        
        best_idx = max(range(len(avg_similarities)), key=lambda i: avg_similarities[i])
        best_answer = answers[best_idx]
        consistency_score = avg_similarities[best_idx]
        
        logger.info(f"Selected answer {best_idx+1} with consistency score: {consistency_score:.3f}")
        return best_answer, consistency_score

    async def _compute_similarity(self, answer1: str, answer2: str) -> float:
        """Compute semantic similarity between two answers."""
        try:
            prompt = f"""Compare these two answers to the same question and rate their semantic similarity on a scale of 0.0 to 1.0.

Answer 1: {answer1}

Answer 2: {answer2}

Consider:
- Do they convey the same key information?
- Are the main facts consistent?
- Minor wording differences are OK

Respond with ONLY a number between 0.0 and 1.0."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at comparing text similarity. Respond with only a number."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=10,
            )

            score_text = response.choices[0].message.content.strip()
            score = float(score_text)
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.warning(f"Similarity computation failed: {e}")
            return 0.5

    async def verify_answer(
        self,
        query: str,
        answer: str,
        context: str,
    ) -> tuple[bool, str]:
        """Verify if answer is faithful to the context."""
        try:
            prompt = f"""Verify if this answer is fully supported by the provided context.

Context:
{context}

Question: {query}

Answer: {answer}

Is the answer:
1. Fully grounded in the context? (no hallucinations)
2. Accurate based on the sources?
3. Not making claims beyond what's stated?

Respond with:
- "VERIFIED" if fully supported
- "PARTIALLY_VERIFIED" if mostly supported with minor issues
- "NOT_VERIFIED" if contains unsupported claims

Then on a new line, briefly explain why."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert fact-checker. Be strict about verification."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=150,
            )

            result = response.choices[0].message.content.strip()
            lines = result.split('\n', 1)
            
            status = lines[0].strip().upper()
            explanation = lines[1].strip() if len(lines) > 1 else ""
            
            is_verified = status in ["VERIFIED", "PARTIALLY_VERIFIED"]
            
            logger.info(f"Answer verification: {status}")
            return is_verified, explanation

        except Exception as e:
            logger.error(f"Answer verification failed: {e}")
            return True, "Verification failed, assuming valid"
