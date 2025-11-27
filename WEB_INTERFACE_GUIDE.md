# Web Interface Guide

## 🌸 Bouquet Web Interface

A simple, intuitive web interface for your Smart RAG system with chat, document upload, and graph visualization.

## Access

Open your browser and navigate to:

**http://localhost:8000**

## Interface Overview

The interface is divided into two main sections:

### Left Sidebar (400px)
1. **Upload Section** - Drag & drop or click to upload documents
2. **Statistics Panel** - Real-time graph metrics
3. **Chat Interface** - Ask questions and get AI-powered answers

### Right Panel (Main Area)
- **Graph Visualization** - Interactive D3.js-powered knowledge graph
- **Graph Controls** - Refresh and reset zoom controls

## Features

### 📄 Document Upload

**How to Upload:**
- **Drag & Drop**: Drag files from your computer into the upload area
- **Click to Browse**: Click "Choose Files" button to select files
- **Multiple Files**: Upload multiple documents at once

**Supported Formats:**
- `.txt` - Plain text files
- `.md` - Markdown files
- ⚠️ **PDF support coming soon**

**Process:**
1. Upload your documents (this may take 30-60 seconds per document as it processes with OpenAI)
2. Wait for the success message
3. Click "🔄 Rebuild Graph" to build the knowledge graph
4. Wait for confirmation message (may take 1-2 minutes for large documents)

### 💬 Chat Interface

**How to Use:**
1. Type your question in the input field at the bottom
2. Press Enter or click "Send"
3. View the AI-generated answer with source citations

**Features:**
- Natural language question answering
- Source attribution with similarity scores
- Conversation history
- Real-time processing indicators

**Example Questions:**
- "What is artificial intelligence?"
- "Summarize the main points in the documents"
- "What are the relationships between X and Y?"

### 🕸️ Graph Visualization

**Node Types & Colors:**
- 🟣 **Purple (Large)**: Documents
- 🟣 **Dark Purple (Larger)**: Communities (groups of related entities)
- 🟢 **Green (Medium)**: Entities (people, places, concepts)
- 🔵 **Blue (Small)**: Chunks (text segments)

**Interactions:**
- **Hover**: See detailed information about nodes and edges
- **Click & Drag**: Move nodes around to explore relationships
- **Scroll**: Zoom in/out
- **Pan**: Click and drag empty space to move the entire graph

**Controls:**
- **Refresh Graph**: Reload graph data from the database
- **Reset Zoom**: Return to default view

**Edge/Relationship Types:**
- `HAS_CHUNK`: Document contains chunk
- `CONTAINS_ENTITY`: Chunk contains entity
- `RELATED`: Entities are related (weighted by similarity)
- `BELONGS_TO`: Entity/Community belongs to higher-level community
- `PART_OF`: Community is part of parent community

### 📊 Statistics Panel

Real-time metrics:
- **Documents**: Total uploaded documents
- **Entities**: Extracted entities (people, places, concepts)
- **Chunks**: Text segments created
- **Communities**: Detected entity clusters

Updates automatically every 30 seconds.

## Typical Workflow

### First Time Setup
1. **Start Services**: `make up` (already done ✓)
2. **Open Browser**: Navigate to http://localhost:8000
3. **Upload Documents**: Add your first documents
4. **Rebuild Graph**: Click the rebuild button
5. **Explore**: View the graph and start asking questions

### Regular Usage
1. **Upload New Documents**: Drag & drop files as needed
2. **Rebuild**: Click rebuild after uploading (combines new + existing)
3. **Query**: Ask questions via chat
4. **Visualize**: Explore graph relationships
5. **Iterate**: Upload more documents and rebuild as needed

## API Endpoints (Backend)

The web interface uses these API endpoints:

### Document Operations
- `POST /api/v1/documents/upload` - Upload files
- `POST /api/v1/documents/text` - Create from text

### Query Operations
- `POST /api/v1/query` - Ask questions (with LLM answer)
- `POST /api/v1/query/search` - Search only (no LLM)

### Graph Operations
- `GET /api/v1/graph/stats` - Get statistics
- `GET /api/v1/graph/visualize` - Get graph data (nodes & edges)
- `POST /api/v1/graph/rebuild` - Rebuild hierarchy
- `GET /api/v1/graph/communities` - List communities

### System
- `GET /health` - Health check

## Tips & Best Practices

### Document Upload
- ✅ Upload related documents together
- ✅ Use descriptive filenames
- ✅ Keep documents focused on specific topics
- ⚠️ Large files may take time to process

### Graph Building
- ⚠️ Rebuild after uploading new documents
- ⚠️ Rebuilding processes ALL documents (not just new ones)
- ✅ Monitor chat for rebuild status messages
- ⚠️ Large knowledge bases may take several minutes to rebuild

### Querying
- ✅ Ask specific questions
- ✅ Use natural language
- ✅ Check source citations for accuracy
- ✅ Refine questions based on initial results

### Graph Visualization
- ✅ Use zoom for large graphs
- ✅ Drag nodes to see hidden connections
- ✅ Hover over nodes for full details
- ⚠️ Very large graphs (>500 nodes) may be slow

## Troubleshooting

### Web Interface Not Loading
- Check services are running: `docker compose ps`
- Check application logs: `docker compose logs app`
- Verify port 8000 is not in use: `lsof -i :8000`

### Upload Not Working
- Check CORS is enabled (should be by default)
- Check file size limits in backend config
- Verify OpenAI API key is set in `.env`

### Graph Not Showing
- Upload documents first
- Click "Rebuild Graph" and wait for completion
- Check that Neo4j is running: http://localhost:7474
- Click "Refresh Graph" button

### Chat Not Responding
- Verify OpenAI API key in `.env` file
- Check you have OpenAI credits available
- Check backend logs for errors: `docker compose logs app`

### Graph Visualization Issues
- Try "Reset Zoom" button
- Refresh the page
- Check browser console for JavaScript errors (F12)

## Browser Support

Tested and working on:
- ✅ Chrome/Chromium (recommended)
- ✅ Firefox
- ✅ Edge
- ✅ Safari

Requires JavaScript enabled.

## Technology Stack

### Frontend
- **HTML5/CSS3**: Modern, responsive layout
- **Vanilla JavaScript**: No framework dependencies
- **D3.js v7**: Graph visualization library
- **CSS Grid**: Responsive layout

### Backend Integration
- **Fetch API**: RESTful API communication
- **WebSockets**: Not used (could be added for real-time updates)

## Next Steps

### Enhancements You Could Add
- Authentication/login system
- Multiple knowledge base support
- Export graph as image
- Advanced filtering (by entity type, date, etc.)
- Collaborative features (multi-user)
- Saved queries/bookmarks
- Graph search by node name
- Customizable graph colors/sizes

### Performance Optimization
- Pagination for large graphs
- Virtual scrolling for chat history
- Lazy loading of graph nodes
- Caching of API responses

## Support

- **Documentation**: Check `docs/` folder
- **API Docs**: http://localhost:8000/docs
- **Neo4j Browser**: http://localhost:7474
- **Logs**: `docker compose logs -f app`

## Related Files

- **Frontend**: `static/index.html`, `static/app.js`
- **Backend**: `app/main.py`, `app/api/graph.py`
- **Config**: `.env`, `docker-compose.yml`
- **Documentation**: `README.md`, `FEATURES.md`

---

**Enjoy exploring your knowledge graph! 🌸**
