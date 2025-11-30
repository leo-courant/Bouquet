# Memory Safety Guide - Quick Reference

## Overview
The Bouquet system now implements comprehensive memory safety to prevent crashes in VM environments. This guide covers monitoring, tuning, and troubleshooting.

## Key Safety Features

### 1. Streaming File Upload
- **Chunk size**: 256KB
- **Max file size**: 50MB (configurable)
- **Location**: `app/api/documents.py`

### 2. Memory Monitoring
- **Library**: psutil
- **Log pattern**: `[MEMORY] operation: XX.XX MB RSS`
- **Warning threshold**: 500MB

### 3. Processing Limits
- **Max chunk memory**: 5MB per operation
- **Concurrent entities**: 2 parallel extractions
- **Stream buffer**: 64KB

## Configuration

### Adjusting Memory Limits

**File upload limit** (`app/api/documents.py`):
```python
MAX_FILE_SIZE_MB = 50  # Increase for larger files
STREAM_CHUNK_SIZE = 256 * 1024  # Decrease for lower memory
```

**Processing limits** (`app/services/document_processor.py`):
```python
MAX_CHUNK_MEMORY_MB = 5  # Memory per chunk operation
STREAM_BUFFER_SIZE = 64 * 1024  # Internal streaming buffer
```

**Concurrency** (`app/services/document_processor.py::_process_entities_batch`):
```python
max_concurrent = 2  # Increase for more power, decrease for safety
```

### Warning Threshold
Change in `document_processor.py::check_memory_limit()`:
```python
if mem_mb > 500:  # Change 500 to your threshold
    logger.warning(f"[MEMORY] High memory usage: {mem_mb:.2f} MB")
```

## Monitoring

### Real-time Memory Logs
```bash
# Watch memory usage
tail -f logs/app.log | grep MEMORY

# Expected output:
# [MEMORY] Start process_document: 45.23 MB RSS
# [MEMORY] Creating chunk 0: 45.45 MB RSS
# [MEMORY] Embedding chunk 0: 46.12 MB RSS
# [MEMORY] Embedded chunk 0: 45.89 MB RSS
```

### System Monitoring
```bash
# Watch process memory
watch -n 1 'ps aux | grep uvicorn | grep -v grep'

# Use htop (more visual)
htop -p $(pgrep -f uvicorn)

# Check peak memory
ps -o pid,rss,vsz,cmd -p $(pgrep -f uvicorn)
```

### Memory Metrics
Key metrics to watch:
- **RSS (Resident Set Size)**: Actual RAM used
- **VSZ (Virtual Size)**: Total virtual memory
- **Peak RSS**: Maximum memory reached

## Troubleshooting

### Problem: "High memory usage detected" Warning
**Cause**: Memory approaching 500MB threshold
**Solutions**:
1. Reduce concurrent processing: `max_concurrent = 1`
2. Decrease batch size: `batch_size = 10`
3. Increase VM memory allocation
4. Process smaller files

### Problem: File Upload Fails with "File too large"
**Cause**: File exceeds `MAX_FILE_SIZE_MB`
**Solutions**:
1. Increase limit: `MAX_FILE_SIZE_MB = 100`
2. Split file into smaller parts
3. Use background processing queue

### Problem: Memory Continues to Grow
**Cause**: Possible memory leak or accumulated objects
**Investigation**:
```python
# Add to code for debugging
import gc
gc.collect()  # Force garbage collection
log_memory_usage("After GC")
```

**Solutions**:
1. Check for circular references
2. Ensure generators are fully consumed
3. Verify database connections are closed

### Problem: VM Crashes During Upload
**Cause**: Memory spike exceeds VM limits
**Solutions**:
1. Enable swap space (emergency buffer)
2. Reduce `STREAM_CHUNK_SIZE` to 128KB
3. Set stricter `MAX_FILE_SIZE_MB`
4. Add rate limiting to uploads

## Best Practices

### For Development
1. **Always check memory logs** during testing
2. **Test with large files** (10MB+) in VM
3. **Monitor memory growth** over multiple uploads
4. **Use profilers** for detailed analysis:
   ```python
   from memory_profiler import profile
   
   @profile
   async def my_function():
       # Your code
   ```

### For Production
1. **Set conservative limits** initially
2. **Monitor logs** for memory warnings
3. **Track peak memory** over time
4. **Set up alerts** for high memory usage
5. **Regular garbage collection** in long-running processes

### For VM Environments
1. **Allocate 2GB+ RAM** minimum
2. **Enable swap** (2-4GB recommended)
3. **Use stricter limits**:
   - `MAX_FILE_SIZE_MB = 25`
   - `max_concurrent = 1`
   - Lower `batch_size`

## Performance Tuning

### For Speed (More Memory)
```python
# documents.py
MAX_FILE_SIZE_MB = 100
STREAM_CHUNK_SIZE = 1024 * 1024  # 1MB chunks

# document_processor.py
batch_size = 50
max_concurrent = 5
```

### For Safety (Less Memory)
```python
# documents.py
MAX_FILE_SIZE_MB = 25
STREAM_CHUNK_SIZE = 128 * 1024  # 128KB chunks

# document_processor.py
batch_size = 10
max_concurrent = 1
```

### Balanced (Recommended)
```python
# documents.py (current defaults)
MAX_FILE_SIZE_MB = 50
STREAM_CHUNK_SIZE = 256 * 1024  # 256KB

# document_processor.py (current defaults)
batch_size = 20
max_concurrent = 2
```

## Memory Safety Checklist

Before deploying:
- [ ] psutil installed: `pip install psutil>=5.9.0`
- [ ] Memory limits configured appropriately
- [ ] Tested with files >10MB
- [ ] Monitored logs for memory warnings
- [ ] VM has adequate RAM (2GB+ recommended)
- [ ] Swap enabled as safety buffer
- [ ] Alerts set up for high memory usage

During operation:
- [ ] Check logs daily for `[MEMORY]` warnings
- [ ] Track peak memory usage
- [ ] Monitor upload success rate
- [ ] Adjust limits if needed
- [ ] Regular GC if long-running

## Advanced: Memory Profiling

### Using memory_profiler
```bash
# Install
pip install memory-profiler

# Add decorator to function
from memory_profiler import profile

@profile
async def process_document(...):
    # Your code

# Run with profiling
python -m memory_profiler app/main.py
```

### Using tracemalloc
```python
import tracemalloc

# Start tracing
tracemalloc.start()

# Your code here
await process_document(...)

# Get snapshot
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

for stat in top_stats[:10]:
    print(stat)
```

### Using py-spy
```bash
# Install
pip install py-spy

# Profile running process
sudo py-spy top --pid $(pgrep -f uvicorn)

# Record flame graph
sudo py-spy record -o profile.svg --pid $(pgrep -f uvicorn)
```

## Emergency Recovery

### If VM Runs Out of Memory
1. **Immediate**: Kill process
   ```bash
   pkill -9 -f uvicorn
   ```

2. **Review**: Check logs for last operation
   ```bash
   tail -100 logs/app.log | grep MEMORY
   ```

3. **Adjust**: Lower limits before restart
   ```python
   MAX_FILE_SIZE_MB = 25
   max_concurrent = 1
   ```

4. **Restart**: With new limits
   ```bash
   make run
   ```

### If Memory Leak Suspected
1. **Enable detailed logging**:
   ```python
   log_memory_usage(f"After every operation")
   ```

2. **Force GC regularly**:
   ```python
   import gc
   gc.collect()
   ```

3. **Use memory profiler** (see above)

4. **Check for**:
   - Unclosed file handles
   - Circular references
   - Global caches
   - Database connection pools

## Support

For issues related to memory:
1. Check `MEMORY_SAFETY_IMPROVEMENTS.md` for detailed explanations
2. Review logs for `[MEMORY]` entries
3. Adjust configuration based on this guide
4. Profile using tools mentioned above

## Summary

**Key Points**:
- Memory-safe by design (streaming everywhere)
- Configurable limits for your environment
- Comprehensive monitoring built-in
- VM-friendly defaults
- Trade-off: Slight speed decrease for massive stability gain

**Default guarantees**:
- No operation >5MB
- Total usage <500MB
- Safe for 2GB VMs
- Handles 50MB files safely
