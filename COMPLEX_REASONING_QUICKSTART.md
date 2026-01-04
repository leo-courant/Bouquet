# Quick Reference: Complex Reasoning Features

## 🚀 Quick Start

### 1. Enable Features (in `.env`)
```bash
ENABLE_CROSS_DOCUMENT_SYNTHESIS=true
ENABLE_COMPARATIVE_ANALYSIS=true
ENABLE_REASONING_CHAINS=true
ENABLE_CITATION_VALIDATION=true
```

### 2. Start the System
```bash
make dev  # or make up for Docker
```

### 3. Test with Sample Queries

## 📝 Example Queries

### Cross-Document Synthesis
**Query:** "What do my documents say about Magic: The Gathering?"

**Before:** Concatenated chunks from different documents
**After:** 
- Identifies common themes across documents
- Notes where documents agree
- Explicitly calls out contradictions
- Synthesizes unified answer with [Document N] citations

---

### Comparative Analysis
**Query:** "Compare White and Blue strategies in MTG"

**Before:** LLM synthesizes unstructured comparison
**After:**
```
**OVERVIEW**
Brief intro to both strategies

**SIMILARITIES**
- Both can control the board [Source 1]
- Both have flying creatures [Source 2]

**DIFFERENCES**
- White focuses on healing [Source 1]
- Blue focuses on card draw [Source 3]

**WHITE - UNIQUE CHARACTERISTICS**
- Angels and Soldiers [Source 1]
- Lifelink and vigilance [Source 2]

**BLUE - UNIQUE CHARACTERISTICS**
- Counterspells [Source 3]
- Manipulation mechanics [Source 4]

**SUMMARY**
Synthesized conclusion
```

---

### Reasoning Chains
**Query:** "How do creatures with deathtouch interact with trample?"

**Shows explicit reasoning:**
```
=== REASONING CHAIN ===

🎯 GOAL: How do creatures with deathtouch interact with trample?

     ↓
📌 STEP 1: What is deathtouch?
   Evidence: 3 sources

     ↓
📌 STEP 2: What is trample?
   Evidence: 2 sources

     ↓
🔗 STEP 3: Semantic Relationships
   • INTERACTS_WITH: deathtouch + trample
   • ELABORATES: combat damage rules

     ↓
✅ FINAL ANSWER
```

---

### Citation Validation
**Any Query** → Citations are now validated!

**Validation Process:**
1. Extract all [Source N] citations
2. Map claims to citations
3. Verify each claim is supported by cited source
4. Report validation score
5. Auto-correct invalid citations

**Metadata includes:**
- `citation_validation_score`: 0.0-1.0
- `citation_valid`: true/false
- Issues list if invalid

---

## 🔍 API Response Metadata

### New Metadata Fields

```json
{
  "answer": "...",
  "sources": [...],
  "metadata": {
    // Existing fields...
    "confidence": 0.87,
    
    // NEW: Complex reasoning metadata
    "cross_document_synthesis": true,
    "num_documents": 3,
    "comparative_analysis": true,
    "comparison_targets": "White vs Blue",
    "reasoning_chain_steps": 4,
    "citation_validation_score": 0.95,
    "citation_valid": true
  }
}
```

---

## 🎯 Service Details

### CrossDocumentSynthesizer
**When activated:** Query retrieves chunks from 2+ documents
**Output:** Unified answer with document-level insights
**Key feature:** Identifies and explains contradictions

### ComparativeAnalyzer
**When activated:** Query contains "compare", "vs", "difference", etc.
**Output:** Structured comparison table
**Key feature:** Systematic side-by-side analysis

### ReasoningChainBuilder
**When activated:** Multi-hop query or query decomposition used
**Output:** Explicit reasoning steps
**Key feature:** Transparent reasoning path

### CitationValidator
**When activated:** Answer contains [Source N] citations
**Output:** Validation score + corrected answer if needed
**Key feature:** Prevents citation misattribution

---

## 🐛 Troubleshooting

### Feature Not Activating?

**Check 1:** Environment variables set?
```bash
grep "ENABLE_CROSS_DOCUMENT" .env
```

**Check 2:** Config loading correctly?
```python
from app.core.config import get_settings
settings = get_settings()
print(settings.enable_cross_document_synthesis)
```

**Check 3:** Service initialized in dependencies?
```bash
grep "cross_document_synthesizer" app/core/dependencies.py
```

### Performance Issues?

**Too slow?** Disable some features:
```bash
# Keep only citation validation
ENABLE_CROSS_DOCUMENT_SYNTHESIS=false
ENABLE_COMPARATIVE_ANALYSIS=false
ENABLE_REASONING_CHAINS=false
ENABLE_CITATION_VALIDATION=true
```

**LLM costs high?** These features make additional LLM calls:
- Cross-doc synthesis: +1-2 calls per query (if multi-doc)
- Comparative analysis: +1 call (if comparison query)
- Reasoning chain: +1 call for explanation
- Citation validation: +N calls (N = number of citations)

**Optimize:** Use only when needed or implement caching

---

## 📊 Performance Impact

| Feature | Latency Impact | LLM Calls | When Active |
|---------|---------------|-----------|-------------|
| Cross-Doc Synthesis | +0.5-1s | +1-2 | Multi-document results |
| Comparative Analysis | +0.5-1s | +1 | Comparison queries |
| Reasoning Chains | +0.3-0.5s | +1 | Multi-hop queries |
| Citation Validation | +0.1s per citation | +N | All answers with citations |

**Total potential overhead:** +1-3s per query (only when features activate)

---

## ✅ Verification Checklist

After integration, verify:

- [ ] All new service files created (4 files)
- [ ] Ultra-advanced query engine updated
- [ ] Dependencies configured
- [ ] Config file updated with new options
- [ ] .env.example updated
- [ ] No syntax errors (run: `python3 -m py_compile app/services/*.py`)
- [ ] Config defaults fixed (`min_similarity_threshold=0.7`)
- [ ] Test queries work as expected

---

## 🎓 Best Practices

1. **Enable selectively** - Not all queries need all features
2. **Monitor costs** - Track LLM usage with new features
3. **Cache aggressively** - Use query cache to avoid re-computation
4. **Log metadata** - Use the rich metadata for analytics
5. **Iterate feedback** - Use citation validation scores to improve prompts

---

## 📚 Related Documentation

- **COMPLEX_REASONING_COMPLETE.md** - Full implementation details
- **ACCURACY_IMPROVEMENTS_COMPLETE.md** - All accuracy features
- **ULTRA_ADVANCED_FEATURES.md** - Complete feature list
- **API_EXAMPLES.md** - API usage examples

---

## 💡 Tips for Maximum Accuracy

1. **Upload multiple docs** to test cross-document synthesis
2. **Ask comparison questions** to see comparative analysis
3. **Ask complex queries** to see reasoning chains
4. **Check metadata** to see which features activated
5. **Review citation_validation_score** to assess answer reliability

Your system now provides **transparent, validated, cross-document reasoning**! 🎉
