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
});

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
    const loadingId = addMessage('🤔 Thinking...', 'assistant', true);

    try {
        const startTime = Date.now();
        const response = await fetch(`${API_V1}/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                top_k: 5,
                include_sources: true
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const duration = ((Date.now() - startTime) / 1000).toFixed(1);
        
        // Remove loading message
        removeMessage(loadingId);
        
        // Add response with metadata
        let answer = data.answer;
        if (data.sources && data.sources.length > 0) {
            answer += `\n\n⏱️ Response time: ${duration}s`;
        }
        addMessage(answer, 'assistant', false, data.sources);

    } catch (error) {
        removeMessage(loadingId);
        addMessage(`❌ Error: ${error.message}`, 'system');
        console.error('Query failed:', error);
    }
}

function addMessage(text, type, isLoading = false, sources = null) {
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
                sourceItem.innerHTML = `${idx + 1}. <strong>${docTitle}</strong> (${similarity}% relevant)`;
                sourceItem.dataset.chunkId = source.chunk_id;
                sourcesDiv.appendChild(sourceItem);
            });
            messageDiv.appendChild(sourcesDiv);
            
            // Highlight retrieved chunks in graph
            highlightChunks(sources.map(s => s.chunk_id));
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
            console.error('Failed to load graph');
            return;
        }

        graphData = await response.json();
        renderGraph();
        
    } catch (error) {
        console.error('Error loading graph:', error);
    }
}

function renderGraph() {
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

    // Clear existing elements
    g.selectAll('*').remove();

    // Create force simulation
    const width = +svg.attr('width');
    const height = +svg.attr('height');

    simulation = d3.forceSimulation(graphData.nodes)
        .force('link', d3.forceLink(graphData.edges)
            .id(d => d.id)
            .distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30));

    // Create edges
    const links = g.append('g')
        .selectAll('line')
        .data(graphData.edges)
        .enter().append('line')
        .attr('stroke', '#94a3b8')
        .attr('stroke-width', d => (d.weight ? d.weight * 2 : 1))
        .attr('stroke-opacity', 0.6)
        .attr('marker-end', d => `url(#arrow-${d.type})`);

    // Create nodes
    const nodes = g.append('g')
        .selectAll('circle')
        .data(graphData.nodes)
        .enter().append('circle')
        .attr('r', d => {
            if (d.type === 'Chunk' && highlightedChunks.has(d.id)) {
                return getNodeRadius(d) * 1.5;
            }
            return getNodeRadius(d);
        })
        .attr('fill', d => {
            if (d.type === 'Chunk' && highlightedChunks.has(d.id)) {
                return '#fbbf24';
            }
            return getNodeColor(d);
        })
        .attr('stroke', d => {
            if (d.type === 'Chunk' && highlightedChunks.has(d.id)) {
                return '#f59e0b';
            }
            return '#fff';
        })
        .attr('stroke-width', d => {
            if (d.type === 'Chunk' && highlightedChunks.has(d.id)) {
                return 3;
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
        .data(graphData.nodes)
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
    svg.transition().duration(750).call(
        zoom.transform,
        d3.zoomIdentity
    );
}

// Chunk highlighting
let highlightedChunks = new Set();

function highlightChunks(chunkIds) {
    // Store highlighted chunks
    highlightedChunks = new Set(chunkIds);
    
    // If graph is rendered, update node colors
    if (g && graphData.nodes) {
        g.selectAll('circle')
            .transition()
            .duration(500)
            .attr('fill', d => {
                if (d.type === 'Chunk' && highlightedChunks.has(d.id)) {
                    return '#fbbf24'; // Highlight color (amber)
                }
                return getNodeColor(d);
            })
            .attr('stroke', d => {
                if (d.type === 'Chunk' && highlightedChunks.has(d.id)) {
                    return '#f59e0b'; // Highlight stroke
                }
                return '#fff';
            })
            .attr('stroke-width', d => {
                if (d.type === 'Chunk' && highlightedChunks.has(d.id)) {
                    return 3;
                }
                return 2;
            })
            .attr('r', d => {
                if (d.type === 'Chunk' && highlightedChunks.has(d.id)) {
                    return getNodeRadius(d) * 1.5;
                }
                return getNodeRadius(d);
            });
    }
}

function clearHighlights() {
    highlightedChunks.clear();
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

// Refresh stats periodically
setInterval(loadStats, 30000); // Every 30 seconds
