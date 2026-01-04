"""Cross-document synthesis service for multi-document reasoning."""

from typing import Optional

import openai
from loguru import logger

from app.domain import SearchResult


class CrossDocumentSynthesizer:
    """Service for synthesizing information across multiple documents."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
    ) -> None:
        """Initialize cross-document synthesizer."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        logger.info("Initialized CrossDocumentSynthesizer")

    async def synthesize_answer(
        self,
        query: str,
        sources_by_document: dict[str, list[SearchResult]],
        conflicts: Optional[list[dict]] = None,
    ) -> dict:
        """
        Synthesize answer from multiple documents with explicit cross-document reasoning.
        
        Args:
            query: The user's question
            sources_by_document: Dict mapping document_id to list of SearchResult chunks
            conflicts: Optional list of detected conflicts
            
        Returns:
            Dict with synthesized answer, reasoning, and document-level citations
        """
        
        if len(sources_by_document) <= 1:
            # Single document - no cross-document synthesis needed
            return {
                'synthesized': False,
                'answer': None,
                'reasoning': None,
            }
        
        # Build document summaries
        doc_summaries = []
        for doc_id, chunks in sources_by_document.items():
            combined_content = "\n\n".join([c.content[:300] for c in chunks[:3]])
            doc_summaries.append({
                'document_id': doc_id,
                'content': combined_content,
                'num_chunks': len(chunks),
            })
        
        # Generate synthesis
        synthesis = await self._generate_synthesis(query, doc_summaries, conflicts)
        
        return synthesis

    async def _generate_synthesis(
        self,
        query: str,
        doc_summaries: list[dict],
        conflicts: Optional[list[dict]],
    ) -> dict:
        """Generate synthesized answer across documents."""
        
        # Build context from multiple documents
        context_parts = []
        for i, doc_sum in enumerate(doc_summaries, 1):
            context_parts.append(f"[Document {i}] ({doc_sum['num_chunks']} relevant sections)")
            context_parts.append(doc_sum['content'])
            context_parts.append("")
        
        context = "\n".join(context_parts)
        
        # Add conflict information if present
        conflict_note = ""
        if conflicts:
            conflict_note = f"\n\nNOTE: {len(conflicts)} potential conflicts detected between documents. Acknowledge and explain any contradictions."
        
        prompt = f"""You are synthesizing information from {len(doc_summaries)} different documents to answer a question.

Context from multiple documents:
{context}
{conflict_note}

Question: {query}

Instructions:
1. SYNTHESIZE information across all documents - don't just concatenate
2. Identify COMMON THEMES and AGREEMENTS between documents
3. Note any DIFFERENCES or CONTRADICTIONS explicitly
4. Provide a UNIFIED answer that integrates multiple perspectives
5. Use [Document N] to cite which document supports each point
6. If documents contradict, explain both views and note the discrepancy

Provide:
1. SYNTHESIS: The integrated answer
2. CROSS-DOCUMENT INSIGHTS: What you learned by comparing multiple sources
3. CONTRADICTIONS: Any conflicts found (if applicable)

Answer:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at synthesizing information across multiple documents."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=800,
            )

            answer = response.choices[0].message.content.strip()
            
            # Parse the structured response
            synthesis_data = self._parse_synthesis_response(answer)
            
            logger.info(f"Generated cross-document synthesis from {len(doc_summaries)} documents")
            
            return {
                'synthesized': True,
                'answer': synthesis_data.get('synthesis', answer),
                'insights': synthesis_data.get('insights'),
                'contradictions': synthesis_data.get('contradictions'),
                'num_documents': len(doc_summaries),
            }
            
        except Exception as e:
            logger.error(f"Failed to generate synthesis: {e}")
            return {
                'synthesized': False,
                'answer': None,
                'error': str(e),
            }

    def _parse_synthesis_response(self, response: str) -> dict:
        """Parse structured synthesis response."""
        sections = {}
        current_section = None
        current_content = []
        
        for line in response.split('\n'):
            line = line.strip()
            
            # Check for section headers
            if line.startswith('SYNTHESIS:'):
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'synthesis'
                current_content = [line.replace('SYNTHESIS:', '').strip()]
            elif line.startswith('CROSS-DOCUMENT INSIGHTS:'):
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'insights'
                current_content = [line.replace('CROSS-DOCUMENT INSIGHTS:', '').strip()]
            elif line.startswith('CONTRADICTIONS:'):
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'contradictions'
                current_content = [line.replace('CONTRADICTIONS:', '').strip()]
            elif current_section and line:
                current_content.append(line)
        
        # Add last section
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        
        # If no structured format found, treat entire response as synthesis
        if not sections:
            sections['synthesis'] = response
        
        return sections

    async def compare_documents(
        self,
        query: str,
        doc1_chunks: list[SearchResult],
        doc2_chunks: list[SearchResult],
    ) -> dict:
        """
        Generate explicit comparison between two documents.
        
        Useful for queries like "Compare X and Y" or "What's the difference between..."
        """
        
        doc1_content = "\n".join([c.content[:400] for c in doc1_chunks[:3]])
        doc2_content = "\n".join([c.content[:400] for c in doc2_chunks[:3]])
        
        prompt = f"""Compare and contrast the following two documents regarding: {query}

Document 1:
{doc1_content}

Document 2:
{doc2_content}

Provide a structured comparison:

SIMILARITIES:
- [List key points where documents agree]

DIFFERENCES:
- [List key points where documents differ]

UNIQUE TO DOCUMENT 1:
- [Information only in Document 1]

UNIQUE TO DOCUMENT 2:
- [Information only in Document 2]

CONCLUSION:
[Brief synthesis of the comparison]"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at comparing and contrasting documents."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=700,
            )

            comparison = response.choices[0].message.content.strip()
            
            logger.info("Generated document comparison")
            
            return {
                'comparison': comparison,
                'doc1_chunks': len(doc1_chunks),
                'doc2_chunks': len(doc2_chunks),
            }
            
        except Exception as e:
            logger.error(f"Failed to generate comparison: {e}")
            return {
                'comparison': None,
                'error': str(e),
            }

    def group_sources_by_document(
        self,
        sources: list[SearchResult],
    ) -> dict[str, list[SearchResult]]:
        """Group search results by their source document."""
        
        by_document = {}
        
        for source in sources:
            doc_id = source.document_id
            if doc_id not in by_document:
                by_document[doc_id] = []
            by_document[doc_id].append(source)
        
        logger.debug(f"Grouped {len(sources)} sources into {len(by_document)} documents")
        
        return by_document

    async def identify_document_perspectives(
        self,
        sources_by_document: dict[str, list[SearchResult]],
        query: str,
    ) -> dict:
        """
        Identify different perspectives or viewpoints across documents.
        
        Useful for understanding how different sources approach the same topic.
        """
        
        if len(sources_by_document) < 2:
            return {'perspectives': []}
        
        perspectives = []
        
        for doc_id, chunks in sources_by_document.items():
            # Analyze perspective of this document
            combined = "\n".join([c.content[:200] for c in chunks[:2]])
            
            perspective = await self._extract_perspective(query, doc_id, combined)
            if perspective:
                perspectives.append(perspective)
        
        return {
            'perspectives': perspectives,
            'num_documents': len(sources_by_document),
        }

    async def _extract_perspective(
        self,
        query: str,
        doc_id: str,
        content: str,
    ) -> Optional[dict]:
        """Extract the perspective or viewpoint of a document."""
        
        prompt = f"""Analyze the perspective or viewpoint of this document regarding: {query}

Content:
{content}

Identify:
1. VIEWPOINT: What is this document's main perspective?
2. TONE: Factual/Opinion/Neutral/Biased?
3. KEY POINTS: Main arguments or claims

Brief analysis (2-3 sentences):"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You analyze document perspectives."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=150,
            )

            analysis = response.choices[0].message.content.strip()
            
            return {
                'document_id': doc_id,
                'perspective': analysis,
            }
            
        except Exception as e:
            logger.error(f"Failed to extract perspective: {e}")
            return None
