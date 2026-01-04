// API Configuration
const API_BASE = window.location.origin;
const API_V1 = `${API_BASE}/api/v1`;

// State
let graphData = { nodes: [], edges: [] };
let simulation = null;
let svg = null;
let g = null;
let zoom = null;
let uploadQueue = new Map(); // Track file upload states

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    initializeChat();
    initializeUpload();
    initializeGraph();
    loadStats();
    checkHealth();
    initializeDatabaseControls();
    // initializeAutoCleanup(); // DISABLED: Allow database to persist across sessions
    initializeResizable();
});

// Resizable Sidebar
function initializeResizable() {
    const sidebar = document.getElementById('sidebar');
    const resizeHandle = document.getElementById('resizeHandle');
    const container = document.querySelector('.container');
    
    const MIN_WIDTH = 400; // Minimum sidebar width (starting position)
    let isResizing = false;
    let startX = 0;
    let startWidth = MIN_WIDTH;

    resizeHandle.addEventListener('mousedown', (e) => {
        isResizing = true;
        startX = e.clientX;
        startWidth = sidebar.offsetWidth;
        resizeHandle.classList.add('resizing');
        document.body.style.cursor = 'ew-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;

        const delta = e.clientX - startX;
        const newWidth = startWidth + delta;

        // Only allow expansion to the right (never smaller than MIN_WIDTH)
        if (newWidth >= MIN_WIDTH) {
            container.style.setProperty('--sidebar-width', `${newWidth}px`);
        }
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            resizeHandle.classList.remove('resizing');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });
}

// Auto-cleanup: Clear database when tab/window closes
// NOTE: This function is currently DISABLED to allow database persistence
// To enable auto-cleanup, uncomment the initializeAutoCleanup() call in DOMContentLoaded
function initializeAutoCleanup() {
    // Clear database on page unload (tab close, browser close, navigation away)
    window.addEventListener('beforeunload', async (event) => {
        // Use sendBeacon for reliable cleanup even as page unloads
        const url = `${API_V1}/graph/clear?confirm=true`;
        
        // Try fetch with keepalive first
        try {
            await fetch(url, {
                method: 'DELETE',
                keepalive: true  // Ensures request completes even if page unloads
            });
        } catch (error) {
            console.log('Cleanup on unload:', error);
        }
    });
    
    console.log('Auto-cleanup initialized: Database will be cleared when you close this tab');
}

// Health Check
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();
        document.getElementById('connection-status').textContent = 
            data.status === 'healthy' ? 'Connected' : 'Disconnected';
    } catch (error) {
        document.getElementById('connection-status').textContent = 'Disconnected';
        console.error('Health check failed:', error);
    }
}

// Chat functionality
function initializeChat() {
    const input = document.getElementById('queryInput');
    const sendBtn = document.getElementById('sendBtn');

    sendBtn.addEventListener('click', sendQuery);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendQuery();
    });
}

async function sendQuery() {
    const input = document.getElementById('queryInput');
    const query = input.value.trim();
    
    if (!query) return;

    // Add user message
    addMessage(query, 'user');
    input.value = '';

    // Show loading with animated dots
    const loadingId = addMessage('🤔 Analyzing your question...', 'assistant', true);

    try {
        const startTime = Date.now();
        // Use advanced endpoint for fast queries
        const response = await fetch(`${API_V1}/query/advanced`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                top_k: 3,
                include_sources: true,
                strategy: 'hybrid',
                use_reranking: false,
                use_entity_expansion: false,
                use_community_context: false,
                max_hops: 1,
                enable_feedback: false
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const duration = ((Date.now() - startTime) / 1000).toFixed(1);
        
        // Remove loading message
        removeMessage(loadingId);
        
        // Add response with enhanced metadata
        let answer = data.answer;
        
        // Add accuracy metadata if available
        let metadataStr = `⏱️ ${duration}s`;
        if (data.metadata.confidence !== null && data.metadata.confidence !== undefined) {
            const confidence = (data.metadata.confidence * 100).toFixed(0);
            const level = data.metadata.confidence_level || 'UNKNOWN';
            const confidenceIcon = confidence >= 80 ? '🎯' : confidence >= 60 ? '🎲' : '⚠️';
            metadataStr += ` | ${confidenceIcon} Confidence: ${confidence}% (${level})`;
        }
        if (data.metadata.consistency_score !== null && data.metadata.consistency_score !== undefined) {
            const consistency = (data.metadata.consistency_score * 100).toFixed(0);
            metadataStr += ` | ✓ Consistency: ${consistency}%`;
        }
        if (data.metadata.factuality_score !== null && data.metadata.factuality_score !== undefined) {
            const factuality = (data.metadata.factuality_score * 100).toFixed(0);
            metadataStr += ` | ✔️ Factuality: ${factuality}%`;
        }
        if (data.metadata.num_conflicts && data.metadata.num_conflicts > 0) {
            metadataStr += ` | ⚠️ ${data.metadata.num_conflicts} conflicts resolved`;
        }
        if (data.metadata.refinement_iterations && data.metadata.refinement_iterations > 1) {
            metadataStr += ` | 🔄 ${data.metadata.refinement_iterations} refinements`;
        }
        if (data.metadata.answer_word_count) {
            metadataStr += ` | 📝 ${data.metadata.answer_word_count} words`;
        }
        if (data.metadata.reason === 'below_similarity_threshold') {
            metadataStr += ` | ⚠️ Low similarity (max: ${(data.metadata.max_similarity * 100).toFixed(0)}%)`;
        }
        
        if (data.sources && data.sources.length > 0) {
            answer += `\n\n${metadataStr}`;
        }
        
        // Add message with feedback buttons
        addMessage(answer, 'assistant', false, data.sources, data.metadata, query);

    } catch (error) {
        removeMessage(loadingId);
        addMessage(`❌ Error: ${error.message}`, 'system');
        console.error('Query failed:', error);
    }
}

function addMessage(text, type, isLoading = false, sources = null, metadata = null, query = null) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    const messageId = `msg-${Date.now()}-${Math.random()}`;
    messageDiv.id = messageId;
    messageDiv.className = `message ${type}`;
    
    if (isLoading) {
        messageDiv.innerHTML = `<div class="loading"></div> <span style="margin-left: 5px;">${text}</span>`;
        messageDiv.classList.add('pulse');
    } else {
        // Preserve line breaks in text
        const formattedText = text.replace(/\n/g, '<br>');
        messageDiv.innerHTML = formattedText;
        
        // Add feedback buttons for assistant messages
        if (type === 'assistant' && metadata && query) {
            const feedbackDiv = document.createElement('div');
            feedbackDiv.className = 'feedback-buttons';
            feedbackDiv.innerHTML = `
                <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #e0e0e0;">
                    <span style="font-size: 0.9em; color: #666;">Was this helpful?</span>
                    <button class="feedback-btn" onclick="submitFeedback('${encodeURIComponent(query)}', ${JSON.stringify(metadata).replace(/'/g, "&apos;")}, 5, true, '👍 Very helpful')">👍 Yes</button>
                    <button class="feedback-btn" onclick="submitFeedback('${encodeURIComponent(query)}', ${JSON.stringify(metadata).replace(/'/g, "&apos;")}, 2, false, '👎 Not helpful')">👎 No</button>
                </div>
            `;
            messageDiv.appendChild(feedbackDiv);
        }
        
        // Add sources if available
        if (sources && sources.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.className = 'message-sources';
            sourcesDiv.innerHTML = '<strong>📚 Sources:</strong>';
            sources.forEach((source, idx) => {
                const sourceItem = document.createElement('div');
                sourceItem.className = 'source-item';
                const similarity = (source.score * 100).toFixed(1);
                const docTitle = source.metadata?.document_title || 'Document';
                
                // Ensure chunk_id is a string
                const chunkId = String(source.chunk_id);
                
                sourceItem.innerHTML = `${idx + 1}. <strong>${docTitle}</strong> (${similarity}% relevant)`;
                sourceItem.dataset.chunkId = chunkId;
                sourceItem.title = 'Click to highlight in graph';
                
                console.log('Creating source item:', { idx, chunkId, docTitle });
                
                // Add click handler to highlight this specific source
                sourceItem.addEventListener('click', (e) => {
                    e.stopPropagation();
                    
                    const clickedChunkId = chunkId;
                    const isCurrentlySelected = selectedSourceId === clickedChunkId;
                    
                    console.log('Source item clicked!', { 
                        clickedChunkId, 
                        isCurrentlySelected, 
                        currentSelection: selectedSourceId 
                    });
                    
                    // Remove selected class from all source items
                    document.querySelectorAll('.source-item.selected').forEach(el => {
                        el.classList.remove('selected');
                    });
                    
                    if (isCurrentlySelected) {
                        // Deselecting - clear selection
                        selectedSourceId = null;
                        console.log('Deselected source');
                    } else {
                        // Selecting - add selected class and set ID
                        sourceItem.classList.add('selected');
                        selectedSourceId = clickedChunkId;
                        console.log('Selected source:', clickedChunkId);
                    }
                    
                    // Update graph highlights
                    updateNodeHighlights();
                });
                
                sourcesDiv.appendChild(sourceItem);
            });
            messageDiv.appendChild(sourcesDiv);
            
            // Highlight retrieved chunks in graph
            highlightChunks(sources.map(s => String(s.chunk_id)));
        }
    }
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return messageId;
}

function removeMessage(messageId) {
    const message = document.getElementById(messageId);
    if (message) message.remove();
}

// Upload functionality
function initializeUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const rebuildBtn = document.getElementById('rebuildBtn');

    // Click to upload
    uploadArea.addEventListener('click', (e) => {
        if (e.target !== fileInput) {
            fileInput.click();
        }
    });

    // File selection
    fileInput.addEventListener('change', handleFiles);

    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragging');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragging');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragging');
        fileInput.files = e.dataTransfer.files;
        handleFiles();
    });

    // Rebuild button
    rebuildBtn.addEventListener('click', rebuildGraph);
}

async function handleFiles() {
    const fileInput = document.getElementById('fileInput');
    const files = Array.from(fileInput.files);

    if (files.length === 0) return;

    const queueDiv = document.getElementById('uploadQueue');
    const cardsContainer = document.getElementById('fileCards');
    
    // Show queue
    queueDiv.style.display = 'block';
    
    // Create cards for all files
    for (const file of files) {
        createFileCard(file);
    }

    // Upload files sequentially
    for (const file of files) {
        await uploadFile(file);
    }

    // Clear input
    fileInput.value = '';
    
    // Hide queue after a delay if all complete
    setTimeout(() => {
        const allComplete = Array.from(uploadQueue.values()).every(
            state => state === 'success' || state === 'error'
        );
        if (allComplete) {
            queueDiv.style.display = 'none';
            cardsContainer.innerHTML = '';
            uploadQueue.clear();
        }
    }, 3000);
    
    // Reload stats
    loadStats();
}

function createFileCard(file) {
    const cardsContainer = document.getElementById('fileCards');
    const cardId = `file-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    const card = document.createElement('div');
    card.id = cardId;
    card.className = 'file-card uploading';
    card.innerHTML = `
        <div class="file-card-header">
            <span class="file-icon">📄</span>
            <span class="file-name" title="${file.name}">${file.name}</span>
            <span class="file-status uploading">Queued</span>
        </div>
        <div class="file-progress">
            <div class="file-progress-bar" style="width: 0%"></div>
        </div>
        <div class="file-details">
            <span class="file-size">${formatFileSize(file.size)}</span>
            <span class="file-info"></span>
        </div>
    `;
    
    cardsContainer.appendChild(card);
    uploadQueue.set(file, { cardId, status: 'queued' });
    
    return cardId;
}

function updateFileCard(file, status, progress = 0, details = '') {
    const fileData = uploadQueue.get(file);
    if (!fileData) return;
    
    const card = document.getElementById(fileData.cardId);
    if (!card) return;
    
    fileData.status = status;
    
    const statusBadge = card.querySelector('.file-status');
    const progressBar = card.querySelector('.file-progress-bar');
    const infoSpan = card.querySelector('.file-info');
    const icon = card.querySelector('.file-icon');
    
    // Update card styling
    card.className = 'file-card ' + status;
    
    // Update status badge
    statusBadge.className = 'file-status ' + status;
    switch(status) {
        case 'uploading':
            statusBadge.textContent = 'Uploading';
            icon.textContent = '⬆️';
            break;
        case 'processing':
            statusBadge.textContent = 'Processing';
            icon.textContent = '⚙️';
            break;
        case 'success':
            statusBadge.textContent = 'Complete';
            icon.textContent = '✅';
            break;
        case 'error':
            statusBadge.textContent = 'Failed';
            icon.textContent = '❌';
            break;
    }
    
    // Update progress bar
    progressBar.style.width = `${progress}%`;
    
    // Update details
    if (details) {
        infoSpan.textContent = details;
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    // Update card: uploading
    updateFileCard(file, 'uploading', 10, 'Uploading to server...');
    
    const startMessageId = addMessage(`📤 Uploading: ${file.name}...`, 'system');

    try {
        // Simulate upload progress
        updateFileCard(file, 'uploading', 30, 'Uploading...');
        
        const response = await fetch(`${API_V1}/documents/upload`, {
            method: 'POST',
            body: formData
        });

        updateFileCard(file, 'processing', 60, 'Processing with AI...');

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
            throw new Error(error.detail || `Upload failed: ${response.status}`);
        }

        const data = await response.json();
        
        // Update card: success
        const chunks = data.chunks || 0;
        updateFileCard(file, 'success', 100, `${chunks} chunks created`);
        
        // Remove uploading message
        removeMessage(startMessageId);
        
        // Add success message with details
        addMessage(
            `✓ ${file.name}\n` +
            `   ID: ${data.document_id.substring(0, 8)}...\n` +
            `   Chunks: ${chunks}`,
            'system'
        );
        
        // Refresh graph to include new chunks
        await loadGraph();
        
    } catch (error) {
        // Update card: error
        updateFileCard(file, 'error', 0, error.message);
        
        // Remove uploading message
        removeMessage(startMessageId);
        
        // Add error message
        addMessage(`✗ Failed: ${file.name}\n   ${error.message}`, 'system');
        console.error('Upload error:', error);
    }
}

async function rebuildGraph() {
    const rebuildBtn = document.getElementById('rebuildBtn');
    rebuildBtn.disabled = true;
    rebuildBtn.innerHTML = '<div class="loading" style="display: inline-block; margin-right: 5px;"></div> Rebuilding...';
    rebuildBtn.classList.add('pulse');

    const startMessageId = addMessage('🔨 Starting graph rebuild...', 'system');

    try {
        const startTime = Date.now();
        const response = await fetch(`${API_V1}/graph/rebuild`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error(`Rebuild failed: ${response.status}`);
        }

        const data = await response.json();
        const duration = ((Date.now() - startTime) / 1000).toFixed(1);
        
        // Remove start message
        removeMessage(startMessageId);
        
        // Add success message with details
        addMessage(
            `✓ Graph rebuilt successfully!\n` +
            `   Levels: ${data.levels_created}\n` +
            `   Communities: ${data.total_communities}\n` +
            `   Duration: ${duration}s`,
            'system'
        );
        
        // Refresh stats and graph
        loadStats();
        loadGraph();
        
    } catch (error) {
        removeMessage(startMessageId);
        addMessage(`✗ Rebuild failed: ${error.message}`, 'system');
        console.error('Rebuild error:', error);
    } finally {
        rebuildBtn.disabled = false;
        rebuildBtn.textContent = '🔄 Rebuild Graph';
        rebuildBtn.classList.remove('pulse');
    }
}

// Statistics
async function loadStats() {
    try {
        const response = await fetch(`${API_V1}/graph/stats`);
        if (!response.ok) return;

        const stats = await response.json();
        
        document.getElementById('stat-documents').textContent = stats.documents || 0;
        document.getElementById('stat-entities').textContent = stats.entities || 0;
        document.getElementById('stat-chunks').textContent = stats.chunks || 0;
        document.getElementById('stat-communities').textContent = stats.communities || 0;
        
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

// Graph Visualization
function initializeGraph() {
    const svgElement = document.getElementById('graph-svg');
    const width = svgElement.clientWidth;
    const height = svgElement.clientHeight;

    svg = d3.select('#graph-svg')
        .attr('width', width)
        .attr('height', height);

    // Add zoom behavior
    zoom = d3.zoom()
        .scaleExtent([0.1, 10])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        });

    svg.call(zoom);

    // Create container group
    g = svg.append('g');

    // Add arrow markers for edges
    svg.append('defs').selectAll('marker')
        .data(['RELATED', 'HAS_CHUNK', 'CONTAINS_ENTITY', 'BELONGS_TO', 'PART_OF'])
        .enter().append('marker')
        .attr('id', d => `arrow-${d}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', '#999');

    // Event listeners
    document.getElementById('refreshGraphBtn').addEventListener('click', loadGraph);
    document.getElementById('resetZoomBtn').addEventListener('click', resetZoom);

    // Initialize rectangle selection
    initializeRectangleSelection();

    // Load initial graph
    loadGraph();

    // Handle window resize
    window.addEventListener('resize', () => {
        const newWidth = svgElement.clientWidth;
        const newHeight = svgElement.clientHeight;
        svg.attr('width', newWidth).attr('height', newHeight);
    });
}

async function loadGraph() {
    try {
        const response = await fetch(`${API_V1}/graph/visualize?limit=200`);
        if (!response.ok) {
            console.error('Failed to load graph:', response.status, response.statusText);
            return;
        }

        graphData = await response.json();
        console.log('Loaded graph data:', {
            nodeCount: graphData.nodes?.length || 0,
            edgeCount: graphData.edges?.length || 0,
            sampleNode: graphData.nodes?.[0],
            sampleEdge: graphData.edges?.[0]
        });
        
        renderGraph();
        
    } catch (error) {
        console.error('Error loading graph:', error);
    }
}

function renderGraph() {
    // Stop existing simulation if it exists
    if (simulation) {
        simulation.stop();
    }

    if (!graphData.nodes || graphData.nodes.length === 0) {
        // Clear existing elements
        g.selectAll('*').remove();
        
        // Show empty state
        g.append('text')
            .attr('x', svg.attr('width') / 2)
            .attr('y', svg.attr('height') / 2)
            .attr('text-anchor', 'middle')
            .attr('fill', '#94a3b8')
            .style('font-size', '16px')
            .text('No graph data. Upload documents and rebuild the graph.');
        
        return;
    }

    console.log('Rendering graph with', graphData.nodes.length, 'nodes and', graphData.edges.length, 'edges');

    // Clear existing elements
    g.selectAll('*').remove();

    // Create force simulation
    const width = +svg.attr('width');
    const height = +svg.attr('height');

    // Validate node IDs and create a set for quick lookup
    const validNodes = graphData.nodes.filter(n => n.id);
    const nodeIdSet = new Set(validNodes.map(n => n.id));
    
    // Filter edges to only include those where both source and target exist in our node set
    const validEdges = graphData.edges.filter(e => {
        const sourceId = typeof e.source === 'object' ? e.source.id : e.source;
        const targetId = typeof e.target === 'object' ? e.target.id : e.target;
        return sourceId && targetId && nodeIdSet.has(sourceId) && nodeIdSet.has(targetId);
    });
    
    if (validNodes.length === 0) {
        console.error('No valid nodes with IDs found!');
        return;
    }
    
    console.log(`Valid nodes: ${validNodes.length}/${graphData.nodes.length}, Valid edges: ${validEdges.length}/${graphData.edges.length}`);

    simulation = d3.forceSimulation(validNodes)
        .force('link', d3.forceLink(validEdges)
            .id(d => d.id)
            .distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30));

    // Create edges
    const links = g.append('g')
        .selectAll('line')
        .data(validEdges)
        .enter().append('line')
        .attr('stroke', '#94a3b8')
        .attr('stroke-width', d => (d.weight ? d.weight * 2 : 1))
        .attr('stroke-opacity', 0.6)
        .attr('marker-end', d => `url(#arrow-${d.type})`);

    // Create nodes
    const nodes = g.append('g')
        .selectAll('circle')
        .data(validNodes)
        .enter().append('circle')
        .attr('r', d => {
            if (d.type === 'Chunk') {
                if (d.id === selectedSourceId) {
                    return getNodeRadius(d) * 2;
                }
                if (highlightedChunks.has(d.id)) {
                    return getNodeRadius(d) * 1.5;
                }
            }
            return getNodeRadius(d);
        })
        .attr('fill', d => {
            if (d.type === 'Chunk') {
                if (d.id === selectedSourceId) {
                    return '#ef4444'; // Red for selected
                }
                if (highlightedChunks.has(d.id)) {
                    return '#fbbf24'; // Amber for highlighted
                }
            }
            return getNodeColor(d);
        })
        .attr('stroke', d => {
            if (d.type === 'Chunk') {
                if (d.id === selectedSourceId) {
                    return '#dc2626'; // Dark red stroke
                }
                if (highlightedChunks.has(d.id)) {
                    return '#f59e0b';
                }
            }
            return '#fff';
        })
        .attr('stroke-width', d => {
            if (d.type === 'Chunk') {
                if (d.id === selectedSourceId) {
                    return 4;
                }
                if (highlightedChunks.has(d.id)) {
                    return 3;
                }
            }
            return 2;
        })
        .call(d3.drag()
            .on('start', dragStarted)
            .on('drag', dragged)
            .on('end', dragEnded))
        .on('mouseover', showTooltip)
        .on('mouseout', hideTooltip);

    // Create labels
    const labels = g.append('g')
        .selectAll('text')
        .data(validNodes)
        .enter().append('text')
        .text(d => truncateLabel(d.label))
        .attr('font-size', '10px')
        .attr('dx', 12)
        .attr('dy', 4)
        .attr('fill', '#334155');

    // Update positions on each tick
    simulation.on('tick', () => {
        links
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        nodes
            .attr('cx', d => d.x)
            .attr('cy', d => d.y);

        labels
            .attr('x', d => d.x)
            .attr('y', d => d.y);
    });
}

function getNodeRadius(node) {
    const baseSize = {
        'Document': 12,
        'Community': 15,
        'Entity': 8,
        'Chunk': 6
    };
    return baseSize[node.type] || 8;
}

function getNodeColor(node) {
    const colors = {
        'Document': '#667eea',
        'Community': '#764ba2',
        'Entity': '#4ade80',
        'Chunk': '#60a5fa'
    };
    return colors[node.type] || '#94a3b8';
}

function truncateLabel(label, maxLength = 20) {
    if (!label) return 'Unknown';
    return label.length > maxLength ? label.substring(0, maxLength) + '...' : label;
}

// Drag functions
function dragStarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}

function dragEnded(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
}

// Tooltip functions
function showTooltip(event, d) {
    const tooltip = document.getElementById('tooltip');
    
    let content = `<h4>${d.label}</h4>`;
    content += `<div><strong>Type:</strong> ${d.type}</div>`;
    
    if (d.entityType) content += `<div><strong>Entity Type:</strong> ${d.entityType}</div>`;
    if (d.level !== undefined) content += `<div><strong>Level:</strong> ${d.level}</div>`;
    if (d.summary) content += `<div><strong>Summary:</strong> ${d.summary}</div>`;
    if (d.content) content += `<div><strong>Content:</strong> ${d.content}</div>`;
    
    tooltip.innerHTML = content;
    tooltip.style.display = 'block';
    tooltip.style.left = (event.pageX + 10) + 'px';
    tooltip.style.top = (event.pageY + 10) + 'px';
}

function hideTooltip() {
    const tooltip = document.getElementById('tooltip');
    tooltip.style.display = 'none';
}

function resetZoom() {
    // Fit all nodes in view with optimal scaling
    if (!graphData.nodes || graphData.nodes.length === 0) {
        svg.transition().duration(750).call(
            zoom.transform,
            d3.zoomIdentity
        );
        return;
    }
    
    // Calculate bounds of all nodes
    const nodes = graphData.nodes.filter(n => n.x !== undefined && n.y !== undefined);
    if (nodes.length === 0) {
        svg.transition().duration(750).call(
            zoom.transform,
            d3.zoomIdentity
        );
        return;
    }
    
    const xExtent = d3.extent(nodes, d => d.x);
    const yExtent = d3.extent(nodes, d => d.y);
    
    const width = +svg.attr('width');
    const height = +svg.attr('height');
    
    // Calculate bounds with node radii included
    const maxRadius = Math.max(...nodes.map(n => getNodeRadius(n)));
    const padding = maxRadius + 40; // Include node size plus extra padding
    
    const dx = xExtent[1] - xExtent[0] + padding * 2;
    const dy = yExtent[1] - yExtent[0] + padding * 2;
    const x = (xExtent[0] + xExtent[1]) / 2;
    const y = (yExtent[0] + yExtent[1]) / 2;
    
    // Calculate scale to fit all nodes perfectly
    const scale = Math.min(
        width / dx,
        height / dy
    );
    
    const transform = d3.zoomIdentity
        .translate(width / 2, height / 2)
        .scale(scale)
        .translate(-x, -y);
    
    svg.transition().duration(750).call(
        zoom.transform,
        transform
    );
}

// Rectangle selection for zoom
let selectionRect = null;
let selectionStartPoint = null;
let isSelecting = false;

function initializeRectangleSelection() {
    const svgElement = document.getElementById('graph-svg');
    
    // Disable default zoom behavior when Shift is pressed
    svg.on('mousedown.zoom', function(event) {
        if (event.shiftKey) {
            event.stopImmediatePropagation();
        }
    }, true);
    
    svgElement.addEventListener('mousedown', (event) => {
        // Only start selection if Shift key is pressed
        if (!event.shiftKey) return;
        
        // Only start selection on svg background or the g element (not on nodes/edges)
        const isValidTarget = event.target === svgElement || 
                             event.target.tagName === 'svg' || 
                             event.target.tagName === 'g';
        if (!isValidTarget) return;
        
        isSelecting = true;
        const point = d3.pointer(event, svg.node());
        selectionStartPoint = { x: point[0], y: point[1] };
        
        // Create selection rectangle
        if (selectionRect) selectionRect.remove();
        selectionRect = svg.append('rect')
            .attr('class', 'selection-rect')
            .attr('x', selectionStartPoint.x)
            .attr('y', selectionStartPoint.y)
            .attr('width', 0)
            .attr('height', 0)
            .attr('fill', 'rgba(102, 126, 234, 0.1)')
            .attr('stroke', '#667eea')
            .attr('stroke-width', 2)
            .attr('stroke-dasharray', '5,5')
            .style('pointer-events', 'none'); // Don't interfere with mouse events
        
        event.preventDefault();
        event.stopPropagation();
    });
    
    svgElement.addEventListener('mousemove', (event) => {
        if (!isSelecting || !selectionStartPoint) return;
        
        const point = d3.pointer(event, svg.node());
        const x = Math.min(point[0], selectionStartPoint.x);
        const y = Math.min(point[1], selectionStartPoint.y);
        const width = Math.abs(point[0] - selectionStartPoint.x);
        const height = Math.abs(point[1] - selectionStartPoint.y);
        
        selectionRect
            .attr('x', x)
            .attr('y', y)
            .attr('width', width)
            .attr('height', height);
        
        event.preventDefault();
    });
    
    svgElement.addEventListener('mouseup', (event) => {
        if (!isSelecting || !selectionStartPoint) return;
        
        const point = d3.pointer(event, svg.node());
        const x = Math.min(point[0], selectionStartPoint.x);
        const y = Math.min(point[1], selectionStartPoint.y);
        const width = Math.abs(point[0] - selectionStartPoint.x);
        const height = Math.abs(point[1] - selectionStartPoint.y);
        
        // Only zoom if selection is large enough (not just a click)
        if (width > 10 && height > 10) {
            zoomToSelection(x, y, width, height);
        }
        
        // Clean up
        if (selectionRect) {
            selectionRect.remove();
            selectionRect = null;
        }
        selectionStartPoint = null;
        isSelecting = false;
        
        event.preventDefault();
    });
    
    // Cancel selection on Escape or when Shift is released
    document.addEventListener('keyup', (event) => {
        if (event.key === 'Shift' && isSelecting) {
            if (selectionRect) {
                selectionRect.remove();
                selectionRect = null;
            }
            selectionStartPoint = null;
            isSelecting = false;
        }
    });
    
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && isSelecting) {
            if (selectionRect) {
                selectionRect.remove();
                selectionRect = null;
            }
            selectionStartPoint = null;
            isSelecting = false;
        }
    });
}

function zoomToSelection(x, y, width, height) {
    const svgWidth = +svg.attr('width');
    const svgHeight = +svg.attr('height');
    
    // Get current transform
    const currentTransform = d3.zoomTransform(svg.node());
    
    // Convert screen coordinates to graph coordinates
    const graphX = (x - currentTransform.x) / currentTransform.k;
    const graphY = (y - currentTransform.y) / currentTransform.k;
    const graphWidth = width / currentTransform.k;
    const graphHeight = height / currentTransform.k;
    
    // Calculate center of selection in graph coordinates
    const centerX = graphX + graphWidth / 2;
    const centerY = graphY + graphHeight / 2;
    
    // Calculate scale to fit selection
    const scale = Math.min(
        svgWidth / graphWidth,
        svgHeight / graphHeight
    ) * 0.9; // 0.9 for small padding
    
    // Create transform to center and scale the selection
    const transform = d3.zoomIdentity
        .translate(svgWidth / 2, svgHeight / 2)
        .scale(scale)
        .translate(-centerX, -centerY);
    
    svg.transition().duration(750).call(
        zoom.transform,
        transform
    );
}

// Chunk highlighting
let highlightedChunks = new Set();
let selectedSourceId = null;

function highlightChunks(chunkIds) {
    // Store highlighted chunks
    highlightedChunks = new Set(chunkIds);
    selectedSourceId = null; // Clear selected source when new query results come in
    
    // If graph is rendered, update node colors
    updateNodeHighlights();
}

function highlightSelectedSource(chunkId) {
    // Toggle selection - if clicking same source, deselect it
    if (selectedSourceId === chunkId) {
        selectedSourceId = null;
    } else {
        selectedSourceId = chunkId;
    }
    
    updateNodeHighlights();
}

function updateNodeHighlights() {
    if (!g || !graphData.nodes) return;
    
    g.selectAll('circle')
        .transition()
        .duration(500)
        .attr('fill', d => {
            if (d.type === 'Chunk') {
                if (d.id === selectedSourceId) {
                    return '#ef4444'; // Red for selected source
                }
                if (highlightedChunks.has(d.id)) {
                    return '#fbbf24'; // Amber for retrieved chunks
                }
            }
            return getNodeColor(d);
        })
        .attr('stroke', d => {
            if (d.type === 'Chunk') {
                if (d.id === selectedSourceId) {
                    return '#dc2626'; // Dark red stroke for selected
                }
                if (highlightedChunks.has(d.id)) {
                    return '#f59e0b'; // Amber stroke
                }
            }
            return '#fff';
        })
        .attr('stroke-width', d => {
            if (d.type === 'Chunk') {
                if (d.id === selectedSourceId) {
                    return 4;
                }
                if (highlightedChunks.has(d.id)) {
                    return 3;
                }
            }
            return 2;
        })
        .attr('r', d => {
            if (d.type === 'Chunk') {
                if (d.id === selectedSourceId) {
                    return getNodeRadius(d) * 2; // Even larger for selected
                }
                if (highlightedChunks.has(d.id)) {
                    return getNodeRadius(d) * 1.5;
                }
            }
            return getNodeRadius(d);
        });
}

function clearHighlights() {
    highlightedChunks.clear();
    selectedSourceId = null;
    if (g && graphData.nodes) {
        g.selectAll('circle')
            .transition()
            .duration(500)
            .attr('fill', d => getNodeColor(d))
            .attr('stroke', '#fff')
            .attr('stroke-width', 2)
            .attr('r', d => getNodeRadius(d));
    }
}

// Database Controls
function initializeDatabaseControls() {
    const clearDbBtn = document.getElementById('clearDbBtn');
    
    if (!clearDbBtn) return; // Button not found
    
    clearDbBtn.addEventListener('click', async () => {
        if (!confirm('⚠️ WARNING: This will delete ALL data from the database.\n\nThis includes:\n- All documents\n- All chunks\n- All entities\n- All communities\n- All relationships\n\nThis action CANNOT be undone!\n\nAre you absolutely sure?')) {
            return;
        }
        
        if (!confirm('Final confirmation: Delete everything?')) {
            return;
        }
        
        try {
            clearDbBtn.disabled = true;
            clearDbBtn.textContent = 'Clearing...';
            
            const response = await fetch(`${API_V1}/graph/clear?confirm=true`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: 'Failed to clear database' }));
                throw new Error(error.detail);
            }
            
            const result = await response.json();
            
            addMessage('✓ Database cleared successfully', 'system');
            
            // Clear graph visualization
            graphData = { nodes: [], edges: [] };
            renderGraph();
            
            // Reload stats
            await loadStats();
            
            clearDbBtn.textContent = '🗑️ Clear Database';
            clearDbBtn.disabled = false;
            
        } catch (error) {
            addMessage(`✗ Error clearing database: ${error.message}`, 'system');
            clearDbBtn.textContent = '🗑️ Clear Database';
            clearDbBtn.disabled = false;
        }
    });
}

// Refresh stats periodically
setInterval(loadStats, 30000); // Every 30 seconds

// Feedback submission
async function submitFeedback(encodedQuery, metadata, rating, helpful, message) {
    try {
        const query = decodeURIComponent(encodedQuery);
        
        const response = await fetch(`${API_V1}/query/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                rating: rating,
                helpful: helpful,
                feedback_text: null,
                response_metadata: metadata
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Show brief success message
        addMessage(`${message} - Thank you for your feedback!`, 'system');
        
    } catch (error) {
        console.error('Feedback submission failed:', error);
        addMessage(`⚠️ Could not submit feedback: ${error.message}`, 'system');
    }
}
