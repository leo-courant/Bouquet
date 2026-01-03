"""Entity disambiguation and coreference resolution service."""

import json
from typing import Optional

import openai
from loguru import logger

from app.domain import Entity


class EntityDisambiguator:
    """Service for entity disambiguation and coreference resolution."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        threshold: float = 0.8,
    ) -> None:
        """Initialize entity disambiguator."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.threshold = threshold
        logger.info(f"Initialized EntityDisambiguator with model: {model}")

    async def disambiguate_entities(
        self,
        entities: list[Entity],
        context: str,
    ) -> dict[str, str]:
        """Disambiguate entities using context.
        
        Returns mapping of entity name to canonical name.
        """
        if not entities:
            return {}

        entity_names = [e.name for e in entities]
        
        system_prompt = """You are an entity disambiguation expert. Given a list of entity mentions and their context, identify which entities refer to the same real-world entity.

Return a JSON object mapping each entity mention to its canonical (standard) name. If entities are the same, map them to the same canonical name.

Example:
Input: ["Apple", "Apple Inc.", "the company", "Steve Jobs", "Jobs"]
Context: "Apple Inc. was founded by Steve Jobs. The company revolutionized computing. Jobs was a visionary."

Output:
{
  "Apple": "Apple Inc.",
  "Apple Inc.": "Apple Inc.",
  "the company": "Apple Inc.",
  "Steve Jobs": "Steve Jobs",
  "Jobs": "Steve Jobs"
}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Entities: {entity_names}\n\nContext: {context[:2000]}"},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content
            mapping = json.loads(content)
            
            logger.info(f"Disambiguated {len(entities)} entities into {len(set(mapping.values()))} canonical entities")
            return mapping
            
        except Exception as e:
            logger.error(f"Error disambiguating entities: {e}")
            # Fallback: identity mapping
            return {name: name for name in entity_names}

    async def resolve_coreferences(
        self,
        text: str,
    ) -> dict[str, str]:
        """Resolve pronouns and references to entities.
        
        Returns mapping of pronouns/references to entity names.
        """
        system_prompt = """You are a coreference resolution expert. Identify pronouns and references (it, they, the company, this technology, etc.) and map them to the entities they refer to.

Return a JSON object mapping references to entity names.

Example:
Text: "Apple Inc. released the iPhone. It became very popular. The company's stock soared."

Output:
{
  "It": "iPhone",
  "The company": "Apple Inc."
}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text[:2000]},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content
            mapping = json.loads(content)
            
            logger.info(f"Resolved {len(mapping)} coreferences")
            return mapping
            
        except Exception as e:
            logger.error(f"Error resolving coreferences: {e}")
            return {}

    async def generate_entity_aliases(
        self,
        entity: Entity,
        context: str,
    ) -> list[str]:
        """Generate possible aliases for an entity."""
        system_prompt = """Generate a list of alternative names, abbreviations, and common references for the given entity based on the context.

Return a JSON array of alias strings.

Example:
Entity: "United States"
Output: ["US", "USA", "United States of America", "America", "the States"]"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Entity: {entity.name}\nType: {entity.entity_type}\nContext: {context[:1000]}"},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            
            # Handle both array and object with 'aliases' key
            if isinstance(data, dict) and 'aliases' in data:
                aliases = data['aliases']
            elif isinstance(data, list):
                aliases = data
            else:
                aliases = []
            
            # Filter out the original name
            aliases = [a for a in aliases if a.lower() != entity.name.lower()]
            
            logger.debug(f"Generated {len(aliases)} aliases for {entity.name}")
            return aliases[:10]  # Limit to 10 aliases
            
        except Exception as e:
            logger.error(f"Error generating aliases: {e}")
            return []

    def merge_entities(
        self,
        entities: list[Entity],
        canonical_mapping: dict[str, str],
    ) -> list[Entity]:
        """Merge entities based on canonical mapping."""
        # Group entities by canonical name
        canonical_groups: dict[str, list[Entity]] = {}
        
        for entity in entities:
            canonical = canonical_mapping.get(entity.name, entity.name)
            if canonical not in canonical_groups:
                canonical_groups[canonical] = []
            canonical_groups[canonical].append(entity)
        
        # Create merged entities
        merged_entities = []
        for canonical_name, entity_group in canonical_groups.items():
            # Use first entity as base
            base_entity = entity_group[0]
            
            # Merge chunk_ids and aliases
            all_chunk_ids = []
            all_aliases = set()
            
            for entity in entity_group:
                all_chunk_ids.extend(entity.chunk_ids)
                all_aliases.add(entity.name)
                all_aliases.update(entity.aliases)
            
            # Remove canonical name from aliases
            all_aliases.discard(canonical_name)
            
            merged_entity = Entity(
                id=base_entity.id,
                name=canonical_name,
                entity_type=base_entity.entity_type,
                description=base_entity.description,
                chunk_ids=list(set(all_chunk_ids)),
                canonical_name=canonical_name,
                aliases=list(all_aliases),
                confidence=min(e.confidence for e in entity_group),
                metadata=base_entity.metadata,
            )
            
            merged_entities.append(merged_entity)
        
        logger.info(f"Merged {len(entities)} entities into {len(merged_entities)} canonical entities")
        return merged_entities
