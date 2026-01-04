# Debugging Enhancements

## Overview
Comprehensive debugging statements have been added throughout the codebase to provide detailed error tracking and diagnosis. All critical paths now include:
- Entry/exit logging with `[DEBUG]` prefix
- Error type identification with `[ERROR]` prefix
- Exception tracebacks with `[EXCEPTION]` prefix
- Warning messages with `[WARNING]` prefix
- Parameter logging for debugging context
- State tracking at key checkpoints

## Files Enhanced

### Core Services
1. **app/services/document_processor.py**
   - Initialization debugging
   - Chunk creation tracking
   - Embedding generation monitoring
   - Entity extraction detailed logging
   - Memory usage tracking
   - Error context (document ID, chunk index, content length)

2. **app/services/query_engine.py**
   - Query processing flow tracking
   - Search result debugging
   - Similarity threshold filtering logs
   - Context building monitoring
   - Answer generation tracking with LLM details
   - Answer validation logging

3. **app/services/embedding_service.py**
   - Service initialization debugging
   - Cache hit/miss tracking
   - API call monitoring
   - Batch operation logging
   - OpenAI API error details
   - Retry attempt tracking

### API Layer
4. **app/api/documents.py**
   - File upload debugging
   - PDF extraction detailed logging
   - Text file streaming tracking
   - Document processing monitoring
   - Error context (filename, file size, content type)

5. **app/api/query.py**
   - Query endpoint debugging
   - Advanced query parameter tracking
   - Response preparation logging
   - Error handling with query context

### Repository Layer
6. **app/repositories/neo4j_repository.py**
   - Connection establishment tracking
   - Document creation debugging
   - Chunk creation monitoring
   - Embedding storage logging
   - Entity creation/merge tracking
   - Search operation detailed logging
   - Vector index creation debugging
   - Query execution monitoring

### Specialized Services
7. **app/services/entity_extractor.py**
   - Entity extraction LLM call tracking
   - JSON parsing debugging
   - Entity and relationship processing
   - OpenAI API error details
   - Entity/relationship count logging

8. **app/services/graph_builder.py**
   - Graph construction monitoring
   - Edge processing tracking
   - Community detection logging
   - Hierarchical structure building

9. **app/services/advanced_query_engine.py**
   - Component initialization tracking
   - Advanced feature debugging
   - Service dependency logging

### Application Lifecycle
10. **app/main.py**
    - Application startup debugging
    - Database clear operation tracking
    - Shutdown process monitoring
    - Error handling in lifecycle events

11. **app/core/dependencies.py**
    - Dependency injection tracking
    - Service creation monitoring
    - Connection establishment debugging
    - Vector index creation logging

## Debugging Features Added

### 1. Error Type Identification
Every error now logs:
- Exception type (e.g., `TypeError`, `ValueError`, `APIError`)
- Error message
- Full exception traceback
- Context variables (IDs, sizes, parameters)

Example:
```python
logger.error(f"[ERROR] Failed to create chunk {chunk.id}: {type(e).__name__}: {str(e)}")
logger.error(f"[ERROR] Chunk details: document_id={chunk.document_id}, index={chunk.chunk_index}")
logger.exception(f"[EXCEPTION] Chunk creation error:")
```

### 2. Flow Tracking
Function entry/exit logging:
```python
logger.debug(f"[DEBUG] function_name called with param1={param1}, param2={param2}")
# ... function logic ...
logger.debug(f"[DEBUG] function_name completed successfully")
```

### 3. Progress Monitoring
For long-running operations:
```python
if count % 10 == 0:
    logger.debug(f"[DEBUG] Processed {count} items")
```

### 4. State Validation
Critical state checks with warnings:
```python
if not data:
    logger.warning(f"[WARNING] No data found for operation")
```

### 5. API Error Details
OpenAI API errors now include:
- Status code
- Error type
- Request parameters
- Full traceback

### 6. Memory Monitoring
Memory usage tracking at critical points:
```python
log_memory_usage(f"After operation: {details}")
check_memory_limit()
```

## How to Use

### Viewing Debug Logs
Debug logs are written to the configured log file and console. To see all debug messages:
```bash
# View live logs
tail -f logs/app.log | grep DEBUG

# View errors only
tail -f logs/app.log | grep ERROR

# View specific component
tail -f logs/app.log | grep "document_processor"
```

### Log Levels
- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages
- `WARNING`: Warning messages for non-critical issues
- `ERROR`: Error messages for failures
- `EXCEPTION`: Full exception tracebacks

### Troubleshooting with Logs

#### Document Processing Errors
Look for:
- `[DEBUG] process_document called` - Entry point
- `[ERROR] Failed to save document` - Database issues
- `[ERROR] Failed to generate embedding` - API issues
- `[ERROR] Failed to extract entities` - Entity extraction issues

#### Query Errors
Look for:
- `[DEBUG] query called` - Entry point
- `[ERROR] Failed to generate query embedding` - Embedding issues
- `[ERROR] search_similar_chunks failed` - Search issues
- `[ERROR] Answer generation failed` - LLM issues

#### Connection Errors
Look for:
- `[ERROR] Neo4j service unavailable` - Database connection
- `[ERROR] OpenAI API error` - API connectivity
- `[ERROR] Failed to connect to Neo4j` - Configuration issues

## Benefits

1. **Clear Error Location**: Know exactly where errors occur
2. **Error Cause**: Understand why errors happen
3. **Error Context**: See the state when errors occurred
4. **Flow Visibility**: Track execution through complex operations
5. **Performance Monitoring**: Identify slow operations
6. **Debugging Efficiency**: Faster issue resolution
7. **Production Monitoring**: Better observability in production

## Example Error Output

```
[DEBUG] upload_document called: filename=test.pdf, extract_entities=True
[DEBUG] File size: 2.50MB
[DEBUG] Calling extract_text_from_pdf_streaming
[DEBUG] pypdf imported successfully
[DEBUG] PDF has 10 pages
[DEBUG] Processed 10/10 pages
[DEBUG] PDF extraction complete: 15000 characters from 10 pages
[DEBUG] Calling processor.process_text with title=test.pdf
[DEBUG] process_document called: document_id=abc-123, extract_entities=True
[DEBUG] Attempting to save document to repository
[ERROR] Failed to save document abc-123 to database: ConnectionError: Connection refused
[ERROR] Document details: title=test.pdf, content_length=15000
[EXCEPTION] Document save error:
Traceback (most recent call last):
  File "app/services/document_processor.py", line 150, in process_document
    await repository.create_document(document)
ConnectionError: Connection to Neo4j refused at localhost:7687
```

This makes it immediately clear:
- What operation failed (document save)
- Where it failed (document_processor.py line 150)
- Why it failed (connection refused)
- Context (document ID, title, content length)
- Full traceback for deeper investigation
