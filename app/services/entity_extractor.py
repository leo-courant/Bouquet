"""Entity extraction service using LLM."""

import json
from typing import Any

import openai
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.domain import Entity, Relationship


class EntityExtractor:
    """Service for extracting entities and relationships from text using LLM."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        max_entities: int = 50,
    ) -> None:
        """Initialize entity extractor."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_entities = max_entities
        logger.info(f"Initialized EntityExtractor with model: {model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def extract_entities_and_relationships(
        self, text: str
    ) -> tuple[list[Entity], list[Relationship]]:
        """Extract entities and relationships from text."""
        system_prompt = """You are an expert at extracting structured knowledge from text.
Extract named entities and relationships from the provided text.

Return a JSON object with this structure:
{
  "entities": [
    {
      "name": "entity name",
      "type": "PERSON|ORGANIZATION|LOCATION|CONCEPT|EVENT|OTHER",
      "description": "brief description"
    }
  ],
  "relationships": [
    {
      "source": "source entity name",
      "target": "target entity name",
      "type": "relationship type (verb phrase)",
      "description": "brief description"
    }
  ]
}

Guidelines:
- Extract key entities that are central to understanding the text
- Focus on meaningful relationships between entities
- Use descriptive relationship types (e.g., "works_for", "located_in", "causes")
- Keep descriptions concise (1-2 sentences)
- Avoid redundant or trivial entities
"""

        user_prompt = f"Extract entities and relationships from this text:\n\n{text}"

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            # Parse entities
            entities = []
            entity_map = {}
            for ent_data in data.get("entities", [])[:self.max_entities]:
                entity = Entity(
                    name=ent_data["name"],
                    entity_type=ent_data.get("type", "OTHER"),
                    description=ent_data.get("description"),
                )
                entities.append(entity)
                entity_map[entity.name] = entity

            # Parse relationships
            relationships = []
            for rel_data in data.get("relationships", []):
                source_name = rel_data["source"]
                target_name = rel_data["target"]

                # Ensure both entities exist
                if source_name in entity_map and target_name in entity_map:
                    relationship = Relationship(
                        source_entity_id=entity_map[source_name].id,
                        target_entity_id=entity_map[target_name].id,
                        relationship_type=rel_data["type"],
                        description=rel_data.get("description"),
                    )
                    relationships.append(relationship)

            logger.info(
                f"Extracted {len(entities)} entities and {len(relationships)} relationships"
            )
            return entities, relationships

        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return [], []

    async def generate_summary(self, text: str, max_length: int = 200) -> str:
        """Generate a concise summary of the text."""
        system_prompt = f"""Generate a concise summary of the provided text in {max_length} characters or less.
Focus on the main topics and key points."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
                max_tokens=100,
            )

            summary = response.choices[0].message.content.strip()
            logger.debug(f"Generated summary: {summary[:50]}...")
            return summary

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return text[:max_length]
