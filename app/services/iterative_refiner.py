"""Iterative refinement service for improving answer quality."""

from typing import Optional

import openai
from loguru import logger

from app.domain import SearchResult


class IterativeRefiner:
    """Service for iteratively refining answers."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        max_iterations: int = 2,
    ) -> None:
        """Initialize iterative refiner."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_iterations = max_iterations
        logger.info(f"Initialized IterativeRefiner with max_iterations={max_iterations}")

    async def refine_answer(
        self,
        query: str,
        initial_answer: str,
        context: str,
        sources: list[SearchResult],
        retrieval_func,  # Function to retrieve more context
    ) -> dict:
        """Iteratively refine answer until complete or max iterations reached."""
        
        current_answer = initial_answer
        refinement_history = []
        
        for iteration in range(self.max_iterations):
            logger.info(f"Refinement iteration {iteration + 1}/{self.max_iterations}")
            
            # Assess if answer is complete
            assessment = await self._assess_completeness(query, current_answer, context)
            
            refinement_history.append({
                'iteration': iteration + 1,
                'answer': current_answer,
                'completeness_score': assessment['completeness'],
                'missing_aspects': assessment.get('missing_aspects', []),
            })
            
            # If complete enough, stop
            if assessment['completeness'] >= 0.85:
                logger.info(f"Answer complete after {iteration + 1} iterations")
                break
            
            # If missing information, try to retrieve more context
            if assessment.get('missing_aspects'):
                logger.info(f"Missing aspects: {assessment['missing_aspects']}")
                
                # Generate focused query for missing information
                focused_query = await self._generate_focused_query(
                    query,
                    assessment['missing_aspects'],
                )
                
                # Retrieve additional context
                try:
                    additional_sources = await retrieval_func(focused_query)
                    
                    if additional_sources:
                        # Add to context
                        additional_context = "\n\n".join([
                            src.content for src in additional_sources[:3]
                        ])
                        
                        # Regenerate answer with enhanced context
                        current_answer = await self._regenerate_answer(
                            query,
                            current_answer,
                            context + "\n\n" + additional_context,
                            assessment['missing_aspects'],
                        )
                    else:
                        logger.info("No additional sources found")
                        break
                        
                except Exception as e:
                    logger.warning(f"Failed to retrieve additional context: {e}")
                    break
            else:
                # Just try to improve the answer
                current_answer = await self._improve_answer(
                    query,
                    current_answer,
                    context,
                )
        
        return {
            'final_answer': current_answer,
            'iterations': len(refinement_history),
            'refinement_history': refinement_history,
            'final_completeness': refinement_history[-1]['completeness_score'] if refinement_history else 0.0,
        }

    async def _assess_completeness(
        self,
        query: str,
        answer: str,
        context: str,
    ) -> dict:
        """Assess if answer completely addresses the query."""
        try:
            prompt = f"""Assess how completely this answer addresses the query.

Query: {query}

Answer: {answer}

Evaluate:
1. Completeness score (0.0 to 1.0)
2. What aspects of the query are not fully addressed?

Format:
COMPLETENESS: [0.0-1.0]
MISSING: [list missing aspects, or "NONE"]"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at evaluating answer quality."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=150,
            )

            result = response.choices[0].message.content.strip()
            
            # Parse result
            lines = result.split('\n')
            completeness = 0.7
            missing_aspects = []
            
            for line in lines:
                if line.startswith('COMPLETENESS:'):
                    try:
                        completeness = float(line.split(':')[1].strip())
                    except:
                        pass
                elif line.startswith('MISSING:'):
                    missing_text = line.split(':', 1)[1].strip()
                    if missing_text != "NONE":
                        missing_aspects = [
                            aspect.strip().strip('-•*')
                            for aspect in missing_text.split(',')
                            if aspect.strip()
                        ]
            
            return {
                'completeness': completeness,
                'missing_aspects': missing_aspects,
            }

        except Exception as e:
            logger.warning(f"Completeness assessment failed: {e}")
            return {'completeness': 0.7, 'missing_aspects': []}

    async def _generate_focused_query(
        self,
        original_query: str,
        missing_aspects: list[str],
    ) -> str:
        """Generate a focused query to retrieve missing information."""
        try:
            missing_text = ", ".join(missing_aspects[:3])
            
            prompt = f"""Generate a focused search query to find information about these missing aspects.

Original Query: {original_query}

Missing Aspects: {missing_text}

Generate a concise search query (one sentence) to find this missing information."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at creating search queries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=50,
            )

            focused_query = response.choices[0].message.content.strip()
            logger.info(f"Generated focused query: {focused_query}")
            return focused_query

        except Exception as e:
            logger.warning(f"Focused query generation failed: {e}")
            return original_query

    async def _regenerate_answer(
        self,
        query: str,
        previous_answer: str,
        enhanced_context: str,
        missing_aspects: list[str],
    ) -> str:
        """Regenerate answer with additional context."""
        try:
            missing_text = ", ".join(missing_aspects)
            
            prompt = f"""Improve this answer using the additional context, specifically addressing the missing aspects.

Query: {query}

Previous Answer:
{previous_answer}

Missing Aspects: {missing_text}

Additional Context:
{enhanced_context[-1500:]}

Generate an improved answer that:
1. Incorporates information from previous answer
2. Addresses the missing aspects
3. Uses the additional context
4. Maintains coherence and clarity"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at synthesizing information."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500,
            )

            improved_answer = response.choices[0].message.content.strip()
            return improved_answer

        except Exception as e:
            logger.error(f"Answer regeneration failed: {e}")
            return previous_answer

    async def _improve_answer(
        self,
        query: str,
        answer: str,
        context: str,
    ) -> str:
        """Improve answer quality without additional retrieval."""
        try:
            prompt = f"""Improve this answer for clarity, completeness, and accuracy.

Query: {query}

Current Answer:
{answer}

Context:
{context[:1500]}

Provide an improved version that:
1. Is more clear and well-structured
2. Better uses information from the context
3. Is more complete
4. Maintains accuracy"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert editor."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500,
            )

            improved = response.choices[0].message.content.strip()
            return improved

        except Exception as e:
            logger.error(f"Answer improvement failed: {e}")
            return answer
