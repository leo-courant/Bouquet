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
        logger.debug(f"[DEBUG] EntityExtractor.__init__ called with model={model}, max_entities={max_entities}")
        try:
            self.client = openai.AsyncOpenAI(api_key=api_key)
            self.model = model
            self.max_entities = max_entities
            logger.info(f"Initialized EntityExtractor with model: {model}")
            logger.debug(f"[DEBUG] EntityExtractor initialized successfully")
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize EntityExtractor: {type(e).__name__}: {str(e)}")
            logger.exception(f"[EXCEPTION] EntityExtractor.__init__ traceback:")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def extract_entities_and_relationships(
        self, text: str
    ) -> tuple[list[Entity], list[Relationship]]:
        """Extract entities and relationships from text."""
        logger.debug(f"[DEBUG] extract_entities_and_relationships called: text_length={len(text)}")
        try:
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

            logger.debug(f"[DEBUG] Calling OpenAI for entity extraction with model {self.model}")
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
            logger.debug(f"[DEBUG] Received response from OpenAI: {len(content)} characters")
            try:
                data = json.loads(content)
                logger.debug(f"[DEBUG] Parsed JSON response successfully")
            except json.JSONDecodeError as json_e:
                logger.error(f"[ERROR] Failed to parse JSON response: {str(json_e)}")
                logger.error(f"[ERROR] Response content: {content[:500]}...")
                raise

            # Parse entities
            entities = []
            entity_map = {}
            raw_entities = data.get("entities", [])
            logger.debug(f"[DEBUG] Extracting {len(raw_entities)} entities (max={self.max_entities})")
            for idx, ent_data in enumerate(raw_entities[:self.max_entities]):
                try:
                    entity = Entity(
                        name=ent_data["name"],
                        entity_type=ent_data.get("type", "OTHER"),
                        description=ent_data.get("description"),
                    )
                    entities.append(entity)
                    entity_map[entity.name] = entity
                    logger.debug(f"[DEBUG] Parsed entity {idx+1}: {entity.name} ({entity.entity_type})")
                except Exception as ent_e:
                    logger.error(f"[ERROR] Failed to parse entity {idx+1}: {type(ent_e).__name__}: {str(ent_e)}")
                    logger.error(f"[ERROR] Entity data: {ent_data}")
                    # Continue with other entities

            # Parse relationships
            relationships = []
            raw_relationships = data.get("relationships", [])
            logger.debug(f"[DEBUG] Extracting {len(raw_relationships)} relationships")
            for idx, rel_data in enumerate(data.get("relationships", [])):
                try:
                    source_name = rel_data["source"]
                    target_name = rel_data["target"]
                    logger.debug(f"[DEBUG] Processing relationship {idx+1}: {source_name} -> {target_name}")

                    # Ensure both entities exist
                    if source_name in entity_map and target_name in entity_map:
                        relationship = Relationship(
                            source_entity_id=entity_map[source_name].id,
                            target_entity_id=entity_map[target_name].id,
                            relationship_type=rel_data["type"],
                            description=rel_data.get("description"),
                        )
                        relationships.append(relationship)
                        logger.debug(f"[DEBUG] Created relationship: {rel_data['type']}")
                    else:
                        logger.warning(f"[WARNING] Skipping relationship {idx+1}: entities not found (source={source_name in entity_map}, target={target_name in entity_map})")
                except Exception as rel_e:
                    logger.error(f"[ERROR] Failed to parse relationship {idx+1}: {type(rel_e).__name__}: {str(rel_e)}")
                    logger.error(f"[ERROR] Relationship data: {rel_data}")
                    # Continue with other relationships

            logger.info(
                f"Extracted {len(entities)} entities and {len(relationships)} relationships"
            )
            logger.debug(f"[DEBUG] Entity extraction completed successfully")
            return entities, relationships

        except openai.APIError as api_e:
            logger.error(f"[ERROR] OpenAI API error during entity extraction: {type(api_e).__name__}: {str(api_e)}")
            logger.error(f"[ERROR] API details: status_code={getattr(api_e, 'status_code', 'N/A')}, type={getattr(api_e, 'type', 'N/A')}")
            logger.error(f"[ERROR] Text length: {len(text)}")
            logger.exception(f"[EXCEPTION] Entity extraction API error:")
            raise
        except Exception as e:
            logger.error(f"[ERROR] Unexpected error during entity extraction: {type(e).__name__}: {str(e)}")
            logger.error(f"[ERROR] Text length: {len(text)}")
            logger.exception(f"[EXCEPTION] Entity extraction error:")
            raise
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
