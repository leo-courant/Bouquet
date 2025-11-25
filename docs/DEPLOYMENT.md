# Deployment Guide

## Prerequisites

- Docker and Docker Compose
- OpenAI API key
- 4GB+ RAM available
- 10GB+ disk space

## Quick Start with Docker Compose

1. **Clone and configure**:
```bash
cd smart_rag
cp .env.example .env
```

2. **Edit `.env` file**:
```env
OPENAI_API_KEY=your-actual-api-key-here
NEO4J_PASSWORD=your-secure-password
```

3. **Edit `docker-compose.yml`** (update Neo4j password):
```yaml
environment:
  - NEO4J_AUTH=neo4j/your-secure-password
```

4. **Start services**:
```bash
docker-compose up -d
```

5. **Check status**:
```bash
docker-compose ps
docker-compose logs -f app
```

6. **Access services**:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474

## Manual Deployment (Without Docker)

### 1. Install Neo4j

Download and install Neo4j 5.14+ from https://neo4j.com/download/

Start Neo4j:
```bash
neo4j start
```

### 2. Setup Python Environment

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e .
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Run Application

```bash
# Development mode
uv run uvicorn app.main:app --reload

# Production mode
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Production Deployment

### Using Docker with Custom Network

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  neo4j:
    image: neo4j:5.14-enterprise
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_ACCEPT_LICENSE_AGREEMENT=yes
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G

  app:
    build: .
    environment:
      - WORKERS=4
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 2G
```

### Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: smart-rag
spec:
  replicas: 3
  selector:
    matchLabels:
      app: smart-rag
  template:
    metadata:
      labels:
        app: smart-rag
    spec:
      containers:
      - name: smart-rag
        image: smart-rag:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: smart-rag-secrets
              key: openai-api-key
        - name: NEO4J_URI
          value: "bolt://neo4j-service:7687"
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: smart-rag-service
spec:
  selector:
    app: smart-rag
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/smart-rag
server {
    listen 80;
    server_name api.yourcompany.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts for long-running queries
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }
}
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| OPENAI_API_KEY | Yes | - | OpenAI API key |
| OPENAI_MODEL | No | gpt-4-turbo-preview | LLM model name |
| OPENAI_EMBEDDING_MODEL | No | text-embedding-3-large | Embedding model |
| NEO4J_URI | No | bolt://localhost:7687 | Neo4j connection URI |
| NEO4J_USER | No | neo4j | Neo4j username |
| NEO4J_PASSWORD | Yes | - | Neo4j password |
| CHUNK_SIZE | No | 1000 | Document chunk size |
| CHUNK_OVERLAP | No | 200 | Chunk overlap size |
| TOP_K_RETRIEVAL | No | 10 | Number of chunks to retrieve |
| MAX_HIERARCHY_LEVELS | No | 3 | Max graph hierarchy depth |
| LOG_LEVEL | No | INFO | Logging level |

## Monitoring

### Health Checks

```bash
# Application health
curl http://localhost:8000/health

# Neo4j health
curl http://localhost:7474/db/data/
```

### Logging

Logs are written to:
- Console (stdout)
- `logs/smart_rag.log` (rotated, 7 days retention)

View logs:
```bash
# Docker
docker-compose logs -f app

# Local
tail -f logs/smart_rag.log
```

### Metrics

Consider integrating:
- Prometheus for metrics collection
- Grafana for visualization
- ELK stack for log aggregation

## Backup and Recovery

### Neo4j Backup

```bash
# Using neo4j-admin
neo4j-admin dump --database=neo4j --to=/backups/neo4j-backup.dump

# Restore
neo4j-admin load --from=/backups/neo4j-backup.dump --database=neo4j --force
```

### Docker Volume Backup

```bash
# Backup Neo4j data
docker run --rm \
  -v smart_rag_neo4j_data:/data \
  -v $(pwd)/backups:/backup \
  ubuntu tar czf /backup/neo4j-data-backup.tar.gz /data
```

## Troubleshooting

### Common Issues

1. **Neo4j connection failed**
   - Check Neo4j is running: `docker-compose ps`
   - Verify credentials in .env
   - Check network connectivity

2. **OpenAI API errors**
   - Verify API key is valid
   - Check rate limits
   - Ensure sufficient credits

3. **Memory issues**
   - Reduce CHUNK_SIZE
   - Increase Docker memory limits
   - Enable pagination for large queries

4. **Slow queries**
   - Check Neo4j indexes: `SHOW INDEXES`
   - Optimize chunk size and overlap
   - Reduce TOP_K_RETRIEVAL

### Debug Mode

Enable debug logging:
```env
LOG_LEVEL=DEBUG
APP_DEBUG=true
```

## Security Best Practices

1. **Never commit secrets**: Use .env files (not in git)
2. **Use HTTPS**: Configure SSL/TLS certificates
3. **Implement authentication**: Add API key validation
4. **Rate limiting**: Prevent abuse
5. **Input validation**: Already implemented with Pydantic
6. **Update dependencies**: Regularly update packages
7. **Network isolation**: Use Docker networks
8. **Firewall rules**: Restrict access to necessary ports

## Performance Tuning

### Neo4j Configuration

```conf
# neo4j.conf
dbms.memory.heap.initial_size=2g
dbms.memory.heap.max_size=4g
dbms.memory.pagecache.size=2g
```

### Application Tuning

```python
# Increase workers
uvicorn app.main:app --workers 4

# Configure connection pooling
NEO4J_MAX_CONNECTION_POOL_SIZE=50
```

### Caching

Consider adding Redis for:
- Embedding cache
- Query result cache
- Session management
