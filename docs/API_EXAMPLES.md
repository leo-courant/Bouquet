# API Usage Examples

## Upload a Document

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.txt" \
  -F "title=My Document"
```

## Create Document from Text

```bash
curl -X POST "http://localhost:8000/api/v1/documents/text" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Sample Document",
    "content": "This is a sample document about AI...",
    "source": "manual_input"
  }'
```

## Query the System

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "top_k": 5,
    "include_sources": true
  }'
```

## Search Without Answer Generation

```bash
curl -X POST "http://localhost:8000/api/v1/query/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "neural networks",
    "top_k": 10
  }'
```

## Get Graph Statistics

```bash
curl -X GET "http://localhost:8000/api/v1/graph/stats"
```

## Rebuild Hierarchical Graph

```bash
curl -X POST "http://localhost:8000/api/v1/graph/rebuild"
```

## List Communities

```bash
# All communities
curl -X GET "http://localhost:8000/api/v1/graph/communities?limit=50"

# Communities at specific level
curl -X GET "http://localhost:8000/api/v1/graph/communities?level=0&limit=50"
```

## Get Related Entities

```bash
curl -X GET "http://localhost:8000/api/v1/query/entities/Machine%20Learning/related?max_hops=2"
```

## List Documents

```bash
curl -X GET "http://localhost:8000/api/v1/documents?limit=100"
```

## Get Document by ID

```bash
curl -X GET "http://localhost:8000/api/v1/documents/{document_id}"
```

## Delete Document

```bash
curl -X DELETE "http://localhost:8000/api/v1/documents/{document_id}"
```

## Python Client Example

```python
import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        # Upload document
        response = await client.post(
            "http://localhost:8000/api/v1/documents/text",
            json={
                "title": "AI Overview",
                "content": "Artificial Intelligence is...",
            }
        )
        print(response.json())
        
        # Query
        response = await client.post(
            "http://localhost:8000/api/v1/query",
            json={
                "query": "What is AI?",
                "top_k": 5,
            }
        )
        result = response.json()
        print(f"Answer: {result['answer']}")
        print(f"Sources: {len(result['sources'])}")

asyncio.run(main())
```

## JavaScript/TypeScript Client Example

```javascript
// Upload document
const uploadResponse = await fetch('http://localhost:8000/api/v1/documents/text', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    title: 'AI Overview',
    content: 'Artificial Intelligence is...',
  }),
});
const uploadResult = await uploadResponse.json();
console.log(uploadResult);

// Query
const queryResponse = await fetch('http://localhost:8000/api/v1/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'What is AI?',
    top_k: 5,
  }),
});
const queryResult = await queryResponse.json();
console.log('Answer:', queryResult.answer);
console.log('Sources:', queryResult.sources.length);
```
