"""Reasoning chain builder for explicit multi-hop reasoning paths."""

from typing import Optional

import openai
from loguru import logger

from app.domain import SearchResult


class ReasoningChainBuilder:
    """Service for building explicit reasoning chains in multi-hop queries."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
    ) -> None:
        """Initialize reasoning chain builder."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        logger.info("Initialized ReasoningChainBuilder")

    async def build_reasoning_chain(
        self,
        query: str,
        sources: list[SearchResult],
        sub_queries: Optional[list[str]] = None,
    ) -> dict:
        """
        Build an explicit reasoning chain showing how information connects.
        
        Args:
            query: The original question
            sources: Retrieved sources with reasoning_path metadata
            sub_queries: Optional list of sub-queries used in decomposition
            
        Returns:
            Dict with reasoning chain, steps, and explanations
        """
        
        # Extract reasoning paths from sources
        reasoning_paths = []
        for source in sources:
            if hasattr(source, 'reasoning_path') and source.reasoning_path:
                reasoning_paths.append({
                    'chunk_id': source.chunk_id,
                    'content_preview': source.content[:200],
                    'path': source.reasoning_path,
                    'score': source.score,
                })
        
        # Build chain structure
        chain = await self._construct_chain(query, reasoning_paths, sub_queries)
        
        # Generate explanation
        explanation = await self._explain_reasoning_chain(query, chain, sources)
        
        return {
            'chain': chain,
            'explanation': explanation,
            'num_steps': len(chain.get('steps', [])),
            'sources_used': len(reasoning_paths),
        }

    async def _construct_chain(
        self,
        query: str,
        reasoning_paths: list[dict],
        sub_queries: Optional[list[str]],
    ) -> dict:
        """Construct the reasoning chain structure."""
        
        chain = {
            'query': query,
            'steps': [],
            'connections': [],
        }
        
        # If we have sub-queries, structure around them
        if sub_queries:
            for i, sub_query in enumerate(sub_queries, 1):
                step = {
                    'step_number': i,
                    'type': 'sub_query',
                    'question': sub_query,
                    'evidence': [],
                }
                
                # Find sources relevant to this sub-query
                for rp in reasoning_paths:
                    # Simple relevance check (could be enhanced)
                    if any(word in rp['content_preview'].lower() 
                           for word in sub_query.lower().split()[:3]):
                        step['evidence'].append({
                            'chunk_id': rp['chunk_id'],
                            'preview': rp['content_preview'],
                            'reasoning': rp['path'],
                        })
                
                chain['steps'].append(step)
        
        # Add relationship-based steps
        semantic_relationships = [
            rp for rp in reasoning_paths 
            if rp['path'] and rp['path'][0].get('type') == 'semantic_relationship'
        ]
        
        if semantic_relationships:
            step = {
                'step_number': len(chain['steps']) + 1,
                'type': 'semantic_traversal',
                'description': 'Following semantic relationships between concepts',
                'relationships': [
                    {
                        'relation_type': rp['path'][0].get('relation'),
                        'description': rp['path'][0].get('description'),
                        'weight': rp['path'][0].get('weight'),
                        'evidence': rp['content_preview'],
                    }
                    for rp in semantic_relationships[:5]
                ],
            }
            chain['steps'].append(step)
        
        # Add entity-based steps
        entity_relationships = [
            rp for rp in reasoning_paths 
            if rp['path'] and rp['path'][0].get('type') == 'entity'
        ]
        
        if entity_relationships:
            step = {
                'step_number': len(chain['steps']) + 1,
                'type': 'entity_traversal',
                'description': 'Following entity relationships',
                'entities': [
                    {
                        'names': rp['path'][0].get('names', []),
                        'evidence': rp['content_preview'],
                    }
                    for rp in entity_relationships[:5]
                ],
            }
            chain['steps'].append(step)
        
        return chain

    async def _explain_reasoning_chain(
        self,
        query: str,
        chain: dict,
        sources: list[SearchResult],
    ) -> str:
        """Generate natural language explanation of the reasoning chain."""
        
        # Build description of the chain
        chain_description = f"Query: {query}\n\n"
        
        for step in chain.get('steps', []):
            step_num = step.get('step_number', 0)
            step_type = step.get('type', 'unknown')
            
            if step_type == 'sub_query':
                chain_description += f"Step {step_num}: Answered sub-question '{step['question']}'\n"
                chain_description += f"  Found {len(step.get('evidence', []))} relevant sources\n\n"
            
            elif step_type == 'semantic_traversal':
                chain_description += f"Step {step_num}: Followed semantic relationships\n"
                relationships = step.get('relationships', [])
                for rel in relationships[:3]:
                    chain_description += f"  - {rel.get('relation_type')}: {rel.get('description', 'N/A')}\n"
                chain_description += "\n"
            
            elif step_type == 'entity_traversal':
                chain_description += f"Step {step_num}: Explored entity connections\n"
                entities = step.get('entities', [])
                for ent in entities[:3]:
                    entity_names = ', '.join(ent.get('names', [])[:3])
                    chain_description += f"  - Entities: {entity_names}\n"
                chain_description += "\n"
        
        prompt = f"""Explain the reasoning process used to answer this question:

{chain_description}

Provide a clear, natural language explanation (2-3 sentences) of how the system reasoned through this question:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You explain reasoning processes clearly and concisely."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=200,
            )

            explanation = response.choices[0].message.content.strip()
            
            logger.info("Generated reasoning chain explanation")
            
            return explanation
            
        except Exception as e:
            logger.error(f"Failed to generate explanation: {e}")
            return "Unable to generate explanation"

    async def visualize_reasoning_chain(
        self,
        chain: dict,
    ) -> str:
        """
        Create a text-based visualization of the reasoning chain.
        
        Useful for debugging and explanation.
        """
        
        lines = ["=== REASONING CHAIN ===\n"]
        
        query = chain.get('query', 'Unknown query')
        lines.append(f"🎯 GOAL: {query}\n")
        
        steps = chain.get('steps', [])
        
        for i, step in enumerate(steps, 1):
            step_type = step.get('type', 'unknown')
            
            if i == 1:
                lines.append("     ↓")
            else:
                lines.append("     ↓")
            
            if step_type == 'sub_query':
                lines.append(f"📌 STEP {i}: {step.get('question')}")
                lines.append(f"   Evidence: {len(step.get('evidence', []))} sources")
            
            elif step_type == 'semantic_traversal':
                lines.append(f"🔗 STEP {i}: Semantic Relationships")
                rels = step.get('relationships', [])
                for rel in rels[:2]:
                    rel_type = rel.get('relation_type', 'UNKNOWN')
                    lines.append(f"   • {rel_type}")
            
            elif step_type == 'entity_traversal':
                lines.append(f"👤 STEP {i}: Entity Connections")
                ents = step.get('entities', [])
                for ent in ents[:2]:
                    entity_names = ', '.join(ent.get('names', [])[:2])
                    lines.append(f"   • {entity_names}")
            
            lines.append("")
        
        lines.append("     ↓")
        lines.append("✅ FINAL ANSWER")
        
        return "\n".join(lines)

    async def validate_reasoning_chain(
        self,
        chain: dict,
        answer: str,
    ) -> dict:
        """
        Validate that the reasoning chain logically leads to the answer.
        
        Returns validation results with confidence score.
        """
        
        # Check if chain has sufficient steps
        num_steps = len(chain.get('steps', []))
        
        if num_steps == 0:
            return {
                'valid': False,
                'confidence': 0.0,
                'reason': 'No reasoning steps found',
            }
        
        # Check if each step has evidence
        steps_with_evidence = sum(
            1 for step in chain.get('steps', [])
            if step.get('evidence') or step.get('relationships') or step.get('entities')
        )
        
        evidence_ratio = steps_with_evidence / num_steps if num_steps > 0 else 0.0
        
        # Use LLM to validate logical flow
        validation = await self._llm_validate_chain(chain, answer)
        
        # Combine metrics
        confidence = (evidence_ratio * 0.4) + (validation.get('score', 0.5) * 0.6)
        
        return {
            'valid': confidence >= 0.6,
            'confidence': confidence,
            'num_steps': num_steps,
            'steps_with_evidence': steps_with_evidence,
            'logical_flow': validation.get('logical', True),
            'issues': validation.get('issues', []),
        }

    async def _llm_validate_chain(
        self,
        chain: dict,
        answer: str,
    ) -> dict:
        """Use LLM to validate logical flow of reasoning chain."""
        
        # Build simplified chain description
        chain_desc = []
        for step in chain.get('steps', []):
            if step.get('type') == 'sub_query':
                chain_desc.append(f"- Asked: {step.get('question')}")
            elif step.get('type') == 'semantic_traversal':
                chain_desc.append(f"- Followed semantic relationships")
            elif step.get('type') == 'entity_traversal':
                chain_desc.append(f"- Explored entity connections")
        
        chain_text = "\n".join(chain_desc)
        
        prompt = f"""Validate if this reasoning chain logically leads to the answer:

Reasoning steps:
{chain_text}

Final answer: {answer}

Is this logical? (YES/NO)
Issues (if any):
Score (0.0-1.0):"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You validate reasoning chains."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=150,
            )

            result = response.choices[0].message.content.strip()
            
            # Parse response
            is_logical = 'YES' in result.upper()
            
            # Extract score
            score = 0.7  # Default
            for line in result.split('\n'):
                if 'score' in line.lower() and ':' in line:
                    try:
                        score = float(line.split(':')[1].strip())
                    except:
                        pass
            
            return {
                'logical': is_logical,
                'score': score,
                'issues': [],
            }
            
        except Exception as e:
            logger.error(f"Failed to validate chain: {e}")
            return {
                'logical': True,
                'score': 0.5,
                'issues': [str(e)],
            }
