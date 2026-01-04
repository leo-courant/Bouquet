# Performance Optimization Guide

## Problem: Slow Query Processing for Simple Documents

### Issue Summary
The ultra-advanced query endpoint runs 18+ processing steps with multiple LLM calls, which is excessive for simple documents (e.g., 4 sentences). This causes:
- Long processing times (60+ seconds)
- Unnecessary API costs
- Poor user experience for simple queries

### Root Causes

1. **Over-Engineering for Simple Queries**: The `/api/v1/query/ultra` endpoint always runs all advanced features:
   - Query reformulation (4 variants)
   - HyDE generation
   - Multiple retrieval strategies
   - Cross-encoder reranking (downloads 90.9MB model on first use)
   - Self-consistency verification (generates multiple answer candidates)
   - Factuality verification
   - Confidence scoring
   - Citation extraction & validation
   - Iterative refinement
   - Cross-document synthesis
   - Comparative analysis
   - Reasoning chain building

2. **Sequential Processing**: Each step waits for the previous one to complete
3. **No Adaptive Behavior**: Doesn't scale down for simple documents/queries

---

## Solutions

### Option 1: Use Simpler Endpoints (Recommended for Small Documents)

For simple documents and queries, use the basic query endpoint instead:

**Basic Query** (`/api/v1/query/`):
```bash
curl -X POST http://localhost:8000/api/v1/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the main topic?",
    "top_k": 5
  }'
```
- Processing time: ~2-5 seconds
- Includes: Basic retrieval + generation
- Good for: Simple fact lookup, single-document queries

**Advanced Query** (`/api/v1/query/advanced`):
```bash
curl -X POST http://localhost:8000/api/v1/query/advanced \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare X and Y",
    "top_k": 10,
    "strategy": "adaptive",
    "use_reranking": true
  }'
```
- Processing time: ~10-20 seconds
- Includes: Multiple strategies, reranking, entity expansion
- Good for: Multi-hop queries, entity-focused questions

**Ultra Query** (`/api/v1/query/ultra`):
```bash
curl -X POST http://localhost:8000/api/v1/query/ultra \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Complex multi-document comparison",
    "top_k": 20,
    "strategy": "adaptive"
  }'
```
- Processing time: ~30-90 seconds
- Includes: ALL advanced features
- Good for: Complex reasoning, multi-document synthesis, high-stakes queries requiring verification

---

### Option 2: Disable Heavy Features

Create a configuration file to control which features are enabled:

**config/query_optimization.yaml**:
```yaml
# Lightweight configuration for simple documents
ultra_query:
  # Retrieval
  max_query_variants: 2  # Reduce from 4
  enable_hyde: false  # Disable HyDE for simple queries
  
  # Verification (most expensive)
  enable_self_consistency: false  # Saves ~10 seconds
  enable_factuality_check: false  # Saves ~5 seconds
  enable_iterative_refinement: false  # Saves ~8 seconds
  
  # Analysis
  enable_cross_document_synthesis: false  # Only needed for multi-doc
  enable_comparative_analysis: false  # Only for comparison queries
  enable_reasoning_chain: false  # Expensive for simple queries
  
  # Reranking
  enable_reranking: true  # Keep for quality
  rerank_top_k: 5  # Reduce from 10
  
  # Citation
  enable_citation_extraction: true  # Keep for transparency
  enable_citation_validation: false  # Expensive validation step
```

---

### Option 3: Adaptive Feature Selection (Best Long-term Solution)

Modify the ultra query engine to intelligently enable features based on:

**Document Characteristics**:
- Document count: If only 1 document, disable cross-document synthesis
- Document length: If < 1000 chars, disable iterative refinement
- Entity count: If < 5 entities, disable entity expansion

**Query Characteristics**:
- Query type: Disable comparative analysis for non-comparison queries
- Query length: Simple queries (< 10 words) skip self-consistency
- Complexity: Use query classifier to determine required features

**Implementation** (in `ultra_advanced_query_engine.py`):
```python
async def _select_features(self, query: str, graph_stats: dict) -> dict:
    """Adaptively select which features to enable."""
    features = {
        'self_consistency': True,
        'factuality_check': True,
        'refinement': True,
        'cross_doc_synthesis': True,
        'comparative_analysis': True,
        'reasoning_chain': True,
    }
    
    # Classify query complexity
    classification = await self.query_classifier.classify_query(query)
    
    # Simple queries
    if classification['complexity'] == 'simple':
        features['self_consistency'] = False
        features['refinement'] = False
        features['reasoning_chain'] = False
    
    # Single document
    if graph_stats.get('Document', 0) <= 1:
        features['cross_doc_synthesis'] = False
    
    # Non-comparison queries
    if classification['query_type'] not in ['COMPARISON', 'ANALYTICAL']:
        features['comparative_analysis'] = False
    
    # Small knowledge base
    if graph_stats.get('Chunk', 0) < 10:
        features['refinement'] = False
        
    return features
```

---

## Performance Impact

### Current Ultra Query (All Features):
```
Retrieval:        ~5 seconds
Reranking:        ~12 seconds (model download first time)
Self-consistency: ~10 seconds
Factuality:       ~5 seconds
Refinement:       ~8 seconds
Citations:        ~5 seconds
Other steps:      ~10 seconds
------------------------
Total:            ~55 seconds
```

### Optimized for Simple Documents:
```
Retrieval:        ~3 seconds
Reranking:        ~2 seconds (model cached)
Generation:       ~2 seconds
Citations:        ~2 seconds
------------------------
Total:            ~9 seconds
```

**Speedup: 6x faster** 🚀

---

## Recommendations

### For Your Current Situation (4-sentence document):

1. **Immediate**: Use `/api/v1/query/` or `/api/v1/query/advanced` instead of `/ultra`
2. **Short-term**: Set environment variables to disable heavy features:
   ```bash
   export ENABLE_SELF_CONSISTENCY=false
   export ENABLE_FACTUALITY_CHECK=false
   export ENABLE_ITERATIVE_REFINEMENT=false
   ```
3. **Long-term**: Implement adaptive feature selection based on document/query complexity

### When to Use Ultra Query:

- ✅ Multiple documents (5+) requiring cross-document synthesis
- ✅ Complex comparison queries across different sources
- ✅ High-stakes scenarios requiring verification (legal, medical, etc.)
- ✅ Queries where transparency and citation validation are critical
- ❌ Simple fact lookup in small documents
- ❌ Single-document Q&A
- ❌ Quick exploratory queries

---

## Monitoring Query Performance

Add this to your logs to track performance:

```python
import time

start = time.time()
response = await ultra_query(request)
duration = time.time() - start

logger.info(f"Query completed in {duration:.1f}s for {len(results)} results")

# Alert if too slow
if duration > 30 and num_documents < 3:
    logger.warning(f"Slow query for simple document: {duration:.1f}s")
```

---

## Additional Optimizations

### 1. Cache Reranking Model
Pre-download the model during startup instead of on-demand:
```python
# In app startup
await reranker._load_model()  # Warm up model
```

### 2. Parallel Processing
Where possible, run independent steps in parallel:
```python
# Instead of sequential
consistency = await check_consistency(answer)
factuality = await check_factuality(answer)

# Use parallel
consistency, factuality = await asyncio.gather(
    check_consistency(answer),
    check_factuality(answer)
)
```

### 3. Smart Caching
Cache results more aggressively for similar queries:
```python
# Cache with fuzzy matching
cache_key = hash(normalize_query(query))
```

---

## Error: JSON Serialization

**Fixed**: Added Pydantic config to `QueryResponse` model to properly serialize enums and UUIDs.

The error `Object of type QueryResponse is not JSON serializable` was caused by missing serialization config. Now fixed with:
```python
class Config:
    json_encoders = {UUID: str}
    use_enum_values = True
```
