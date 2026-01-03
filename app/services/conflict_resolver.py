"""Conflict resolution service for handling contradictory sources."""

from typing import Optional

import openai
from loguru import logger

from app.domain import SearchResult


class ConflictResolver:
    """Service for resolving conflicts between contradictory sources."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
    ) -> None:
        """Initialize conflict resolver."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        logger.info("Initialized ConflictResolver")

    async def detect_conflicts(
        self,
        sources: list[SearchResult],
    ) -> list[dict]:
        """Detect conflicts between retrieved sources."""
        
        conflicts = []
        
        # Compare pairs of sources
        for i in range(len(sources)):
            for j in range(i + 1, min(i + 3, len(sources))):  # Check next 2-3 sources
                conflict = await self._check_conflict_between_sources(
                    sources[i],
                    sources[j],
                )
                
                if conflict:
                    conflicts.append({
                        'source1_id': i,
                        'source2_id': j,
                        'conflict_type': conflict['type'],
                        'description': conflict['description'],
                        'severity': conflict['severity'],
                    })
        
        if conflicts:
            logger.warning(f"Detected {len(conflicts)} conflicts between sources")
        
        return conflicts

    async def _check_conflict_between_sources(
        self,
        source1: SearchResult,
        source2: SearchResult,
    ) -> Optional[dict]:
        """Check if two sources contain conflicting information."""
        try:
            prompt = f"""Do these two text passages contain contradictory or conflicting information?

Passage 1:
{source1.content[:400]}

Passage 2:
{source2.content[:400]}

Respond in this format:
CONFLICT: YES/NO
TYPE: [factual/temporal/opinion/none]
SEVERITY: [high/medium/low]
DESCRIPTION: [brief explanation]

If no conflict, respond with:
CONFLICT: NO"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at detecting contradictions and conflicts."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=150,
            )

            result = response.choices[0].message.content.strip()
            
            if "CONFLICT: NO" in result:
                return None
            
            # Parse conflict
            lines = result.split('\n')
            conflict_dict = {}
            
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    conflict_dict[key] = value
            
            if conflict_dict.get('conflict') == 'YES':
                return {
                    'type': conflict_dict.get('type', 'unknown'),
                    'severity': conflict_dict.get('severity', 'medium'),
                    'description': conflict_dict.get('description', 'Conflicting information detected'),
                }
            
            return None

        except Exception as e:
            logger.warning(f"Conflict detection failed: {e}")
            return None

    async def resolve_conflicts(
        self,
        query: str,
        sources: list[SearchResult],
        conflicts: list[dict],
    ) -> dict:
        """Resolve conflicts and provide guidance for answer generation."""
        
        if not conflicts:
            return {
                'has_conflicts': False,
                'resolution_strategy': 'use_all',
                'guidance': None,
            }
        
        # Categorize conflicts by severity
        high_severity = [c for c in conflicts if c['severity'] == 'high']
        
        resolution = {
            'has_conflicts': True,
            'total_conflicts': len(conflicts),
            'high_severity_conflicts': len(high_severity),
        }
        
        # Determine resolution strategy
        if len(high_severity) > 0:
            # Serious conflicts - need explicit resolution
            resolution['resolution_strategy'] = 'acknowledge_conflict'
            resolution['guidance'] = await self._generate_conflict_guidance(
                query,
                sources,
                conflicts,
            )
        else:
            # Minor conflicts - can synthesize
            resolution['resolution_strategy'] = 'synthesize'
            resolution['guidance'] = "Sources have minor differences. Present both perspectives if relevant."
        
        return resolution

    async def _generate_conflict_guidance(
        self,
        query: str,
        sources: list[SearchResult],
        conflicts: list[dict],
    ) -> str:
        """Generate guidance for handling conflicts in answer."""
        try:
            conflict_desc = "\n".join([
                f"- {c['description']} (severity: {c['severity']})"
                for c in conflicts[:3]  # Top 3 conflicts
            ])
            
            prompt = f"""The retrieved sources contain conflicting information. Provide guidance for answering the query.

Query: {query}

Detected Conflicts:
{conflict_desc}

Provide brief guidance on how to handle these conflicts in the answer. Should we:
- Present both perspectives?
- Note the uncertainty?
- Rely on more authoritative sources?
- Something else?

Keep response under 100 words."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at synthesizing conflicting information."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=150,
            )

            guidance = response.choices[0].message.content.strip()
            return guidance

        except Exception as e:
            logger.error(f"Failed to generate conflict guidance: {e}")
            return "Note: Sources contain conflicting information. Present multiple perspectives."

    async def synthesize_conflicting_sources(
        self,
        query: str,
        sources: list[SearchResult],
        conflicts: list[dict],
    ) -> str:
        """Generate a synthesized answer that acknowledges conflicts."""
        try:
            # Build context from conflicting sources
            context_parts = []
            for i, source in enumerate(sources[:5], 1):
                context_parts.append(f"Source {i}: {source.content[:300]}")
            
            context = "\n\n".join(context_parts)
            
            conflict_note = f"\nNote: {len(conflicts)} conflicts detected between sources."
            
            prompt = f"""Answer this query while acknowledging conflicting information in the sources.

Query: {query}

{context}

{conflict_note}

Guidelines:
- Acknowledge that sources disagree
- Present different perspectives fairly
- Note which claims conflict
- Don't hide the uncertainty
- Be balanced and objective"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at synthesizing conflicting information fairly."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=400,
            )

            answer = response.choices[0].message.content.strip()
            return answer

        except Exception as e:
            logger.error(f"Failed to synthesize conflicting sources: {e}")
            return "The available sources contain conflicting information. I cannot provide a definitive answer."

    def prioritize_sources_by_reliability(
        self,
        sources: list[SearchResult],
        conflicts: list[dict],
    ) -> list[SearchResult]:
        """Prioritize sources based on reliability indicators."""
        
        # Create reliability scores
        for source in sources:
            reliability_score = 1.0
            
            # Check metadata for reliability indicators
            if source.metadata:
                # Boost for authoritative markers
                if 'authority' in source.metadata:
                    reliability_score *= 1.2
                
                # Boost for recent content
                if 'timestamp' in source.metadata or 'date' in source.metadata:
                    reliability_score *= 1.1
                
                # Check if source is involved in conflicts
                source_idx = sources.index(source)
                conflict_count = sum(
                    1 for c in conflicts
                    if c['source1_id'] == source_idx or c['source2_id'] == source_idx
                )
                
                # Penalize sources involved in many conflicts
                if conflict_count > 0:
                    reliability_score *= (0.9 ** conflict_count)
            
            source.metadata['reliability_score'] = reliability_score
        
        # Sort by reliability * relevance
        sources.sort(
            key=lambda s: s.score * s.metadata.get('reliability_score', 1.0),
            reverse=True
        )
        
        return sources
