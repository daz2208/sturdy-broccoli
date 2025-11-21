// Use current origin for Docker compatibility, fallback to localhost for development
const API_BASE = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
    ? window.location.origin
    : (window.location.origin || 'http://localhost:8000');
let token = null;

function toggleLogoutButton(show) {
    const button = document.getElementById('logoutButton');
    if (!button) return;
    if (show) {
        button.classList.remove('hidden');
    } else {
        button.classList.add('hidden');
    }
}

// =============================================================================
// HELPERS
// =============================================================================

async function getErrorMessage(response) {
    /**
     * Extract error message from API response.
     * Tries to parse JSON error detail, falls back to status text.
     */
    try {
        const data = await response.json();
        return data.detail || response.statusText || 'Operation failed';
    } catch {
        return response.statusText || 'Operation failed';
    }
}

function setButtonLoading(button, isLoading, originalText = null) {
    /**
     * Set loading state on a button.
     * Disables button and changes text when loading.
     */
    if (isLoading) {
        button.disabled = true;
        button.dataset.originalText = button.textContent;
        button.textContent = 'Loading...';
        button.style.opacity = '0.6';
    } else {
        button.disabled = false;
        button.textContent = originalText || button.dataset.originalText || button.textContent;
        button.style.opacity = '1';
        delete button.dataset.originalText;
    }
}

// =============================================================================
// AUTH
// =============================================================================

async function login(event) {
    const button = event ? event.target : null;
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    if (button) setButtonLoading(button, true);

    try {
        const res = await fetch(`${API_BASE}/token`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, password})
        });

        if (res.ok) {
            const data = await res.json();
            token = data.access_token;
            localStorage.setItem('token', token);
            document.getElementById('authSection').classList.add('hidden');
            document.getElementById('mainContent').classList.remove('hidden');
            toggleLogoutButton(true);
            showToast('Logged in successfully');
            loadClusters();
        } else {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
        }
    } catch (e) {
        showToast('Login error: ' + e.message, 'error');
    } finally {
        if (button) setButtonLoading(button, false, 'Login');
    }
}

async function register(event) {
    const button = event ? event.target : null;
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    if (button) setButtonLoading(button, true);

    try {
        const res = await fetch(`${API_BASE}/users`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, password})
        });

        if (res.ok) {
            showToast('Registered! Now login.');
        } else {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
        }
    } catch (e) {
        showToast('Registration error: ' + e.message, 'error');
    } finally {
        if (button) setButtonLoading(button, false, 'Register');
    }
}

function logout() {
    token = null;
    localStorage.removeItem('token');
    document.getElementById('mainContent').classList.add('hidden');
    document.getElementById('authSection').classList.remove('hidden');
    toggleLogoutButton(false);
    document.getElementById('username').value = '';
    document.getElementById('password').value = '';
    document.getElementById('uploadForms').innerHTML = '';
    document.getElementById('resultsArea').innerHTML = '';
    document.getElementById('clustersList').innerHTML = '';
    showToast('Logged out');
}

// =============================================================================
// UPLOADS (NO BOARD_ID)
// =============================================================================

function showUploadType(type) {
    const forms = document.getElementById('uploadForms');

    if (type === 'text') {
        forms.innerHTML = `
            <textarea id="textContent" rows="8" placeholder="Paste your content..."></textarea>
            <button onclick="uploadText(event)">Upload Text</button>
        `;
    } else if (type === 'url') {
        forms.innerHTML = `
            <input type="text" id="urlInput" placeholder="https://youtube.com/... or https://example.com/article">
            <button onclick="uploadUrl(event)">Upload URL</button>
            <p style="color: #888; font-size: 0.9rem; margin-top: 5px;">YouTube videos may take 30-120 seconds</p>
        `;
    } else if (type === 'file') {
        forms.innerHTML = `
            <input type="file" id="fileInput" accept=".pdf,.txt,.md,.docx,.mp3,.wav,.m4a,.ogg,.flac,.ipynb,.py,.js,.ts,.java,.cpp,.c,.go,.rs,.html,.css,.json,.csv,.yaml,.yml,.sql,.sh,.xlsx,.xls,.pptx,.zip,.epub,.srt,.vtt">
            <button onclick="uploadFile(event)">Upload File</button>
            <p style="color: #888; font-size: 0.85rem; margin-top: 5px;">
                Supports: PDFs, Jupyter notebooks, code files (40+ languages), Office docs (Excel, PowerPoint, Word), audio files, archives, and more
            </p>
        `;
    } else if (type === 'image') {
        forms.innerHTML = `
            <input type="file" id="imageInput" accept="image/*">
            <input type="text" id="imageDesc" placeholder="Optional description (what is this image for?)">
            <button onclick="uploadImage(event)">Upload Image</button>
        `;
    }
}

async function uploadText(event) {
    const button = event ? event.target : null;
    const content = document.getElementById('textContent').value;

    if (!content.trim()) {
        showToast('Content cannot be empty', 'error');
        return;
    }

    if (button) setButtonLoading(button, true);

    try {
        const res = await fetch(`${API_BASE}/upload_text`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({content})
        });

        if (res.ok) {
            const data = await res.json();
            showToast(`Uploaded! Doc ${data.document_id} → Cluster ${data.cluster_id}`);
            document.getElementById('textContent').value = '';
            loadClusters();
        } else {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
        }
    } catch (e) {
        showToast('Upload error: ' + e.message, 'error');
    } finally {
        if (button) setButtonLoading(button, false, 'Upload Text');
    }
}

async function uploadUrl(event) {
    const button = event ? event.target : null;
    const url = document.getElementById('urlInput').value;

    if (!url.trim()) {
        showToast('URL cannot be empty', 'error');
        return;
    }

    if (button) setButtonLoading(button, true);

    try {
        const res = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({url})
        });

        if (res.ok) {
            const data = await res.json();
            // URL queued for background processing
            showToast(`🌐 URL queued: ${url.substring(0, 50)}...`, 'info');
            document.getElementById('urlInput').value = '';

            // Poll for job status
            pollJobStatus(data.job_id, button, 'Upload URL');
        } else {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
            if (button) setButtonLoading(button, false, 'Upload URL');
        }
    } catch (e) {
        showToast('Upload error: ' + e.message, 'error');
        if (button) setButtonLoading(button, false, 'Upload URL');
    }
}

async function uploadFile(event) {
    const button = event ? event.target : null;
    const file = document.getElementById('fileInput').files[0];

    if (!file) {
        showToast('Please select a file', 'error');
        return;
    }

    if (button) setButtonLoading(button, true);

    try {
        const base64 = await fileToBase64(file);

        const res = await fetch(`${API_BASE}/upload_file`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                filename: file.name,
                content: base64
            })
        });

        if (res.ok) {
            const data = await res.json();
            // File queued for background processing
            showToast(`📤 File queued: ${file.name}`, 'info');
            document.getElementById('fileInput').value = '';

            // Poll for job status
            pollJobStatus(data.job_id, button, 'Upload File');
        } else {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
            if (button) setButtonLoading(button, false, 'Upload File');
        }
    } catch (e) {
        showToast('Upload error: ' + e.message, 'error');
        if (button) setButtonLoading(button, false, 'Upload File');
    }
}

async function uploadImage(event) {
    const button = event ? event.target : null;
    const file = document.getElementById('imageInput').files[0];
    const description = document.getElementById('imageDesc').value;

    if (!file) {
        showToast('Please select an image', 'error');
        return;
    }

    if (button) setButtonLoading(button, true);

    try {
        const base64 = await fileToBase64(file);

        const res = await fetch(`${API_BASE}/upload_image`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                filename: file.name,
                content: base64,
                description: description || null
            })
        });

        if (res.ok) {
            const data = await res.json();
            // Image queued for OCR processing
            showToast(`📸 Image queued: ${file.name}`, 'info');
            document.getElementById('imageInput').value = '';
            document.getElementById('imageDesc').value = '';

            // Poll for job status
            pollJobStatus(data.job_id, button, 'Upload Image');
        } else {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
            if (button) setButtonLoading(button, false, 'Upload Image');
        }
    } catch (e) {
        showToast('Upload error: ' + e.message, 'error');
        if (button) setButtonLoading(button, false, 'Upload Image');
    }
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

// =============================================================================
// CLUSTERS
// =============================================================================

async function loadClusters() {
    try {
        const res = await fetch(`${API_BASE}/clusters`, {
            headers: {'Authorization': `Bearer ${token}`}
        });

        if (res.ok) {
            const data = await res.json();
            displayClusters(data.clusters);
        } else {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
        }
    } catch (e) {
        console.error('Failed to load clusters:', e);
        showToast('Failed to load clusters: ' + e.message, 'error');
    }
}

function displayClusters(clusters) {
    const list = document.getElementById('clustersList');

    if (clusters.length === 0) {
        list.innerHTML = '<p style="color: #666;">No clusters yet. Upload some content!</p>';
        return;
    }

    list.innerHTML = clusters.map(c => `
        <div class="cluster-card">
            <div onclick="loadCluster(${c.id})" style="cursor: pointer;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <h3 style="margin: 0;">${c.name}</h3>
                    <div style="display: flex; gap: 8px;">
                        <button onclick="event.stopPropagation(); editCluster(${c.id}, '${c.name.replace(/'/g, "\\'")}', '${c.skill_level}')" title="Edit Cluster" style="background: none; border: none; cursor: pointer; font-size: 1.2rem; padding: 0;">✏️</button>
                        <button onclick="event.stopPropagation(); deleteCluster(${c.id}, '${c.name.replace(/'/g, "\\'")}');" title="Delete Cluster" style="background: none; border: none; cursor: pointer; font-size: 1.2rem; padding: 0; color: #ff4444;">🗑️</button>
                    </div>
                </div>
                <p style="margin-top: 8px;">${c.doc_count} documents • ${c.skill_level}</p>
                <div class="concepts-list">
                    ${c.primary_concepts.slice(0, 3).map(concept =>
                        `<span class="concept-tag">${concept}</span>`
                    ).join('')}
                </div>
            </div>
            <div style="margin-top: 10px; display: flex; gap: 5px; font-size: 0.85rem;">
                <button onclick="event.stopPropagation(); exportCluster(${c.id}, 'json')" style="padding: 4px 8px; font-size: 0.8rem;" title="Export as JSON">📄 JSON</button>
                <button onclick="event.stopPropagation(); exportCluster(${c.id}, 'markdown')" style="padding: 4px 8px; font-size: 0.8rem;" title="Export as Markdown">📝 MD</button>
            </div>
        </div>
    `).join('');
}

async function loadCluster(clusterId) {
    const query = document.getElementById('searchQuery').value || '*';

    try {
        const res = await fetch(
            `${API_BASE}/search_full?q=${encodeURIComponent(query)}&cluster_id=${clusterId}&top_k=20`,
            {headers: {'Authorization': `Bearer ${token}`}}
        );

        if (res.ok) {
            const data = await res.json();
            displaySearchResults(data.results);
        }
    } catch (e) {
        showToast('Failed to load cluster', 'error');
    }
}

async function editCluster(clusterId, currentName, currentSkillLevel) {
    /**
     * Edit cluster name and skill level.
     * Uses existing PUT /clusters/{id} endpoint.
     */
    // Show modal with form
    const modal = document.createElement('div');
    modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 1000;';
    modal.innerHTML = `
        <div style="background: #1e1e2e; padding: 30px; border-radius: 12px; max-width: 500px; width: 90%;">
            <h3 style="margin-top: 0;">Edit Cluster</h3>

            <label style="display: block; margin-top: 15px;">
                Cluster Name:
                <input type="text" id="editClusterName" value="${currentName}"
                       style="width: 100%; margin-top: 5px; padding: 8px; background: #2a2a3e; border: 1px solid #444; color: #fff; border-radius: 4px;">
            </label>

            <label style="display: block; margin-top: 15px;">
                Skill Level:
                <select id="editClusterSkillLevel" style="width: 100%; margin-top: 5px; padding: 8px; background: #2a2a3e; border: 1px solid #444; color: #fff; border-radius: 4px;">
                    <option value="beginner" ${currentSkillLevel === 'beginner' ? 'selected' : ''}>Beginner</option>
                    <option value="intermediate" ${currentSkillLevel === 'intermediate' ? 'selected' : ''}>Intermediate</option>
                    <option value="advanced" ${currentSkillLevel === 'advanced' ? 'selected' : ''}>Advanced</option>
                </select>
            </label>

            <div style="display: flex; gap: 10px; margin-top: 25px; justify-content: flex-end;">
                <button onclick="this.closest('div').parentElement.parentElement.remove()"
                        style="padding: 10px 20px; background: #555; border: none; color: #fff; border-radius: 4px; cursor: pointer;">
                    Cancel
                </button>
                <button onclick="saveClusterChanges(${clusterId}, this.closest('div').parentElement.parentElement)"
                        style="padding: 10px 20px; background: #00d4ff; border: none; color: #000; border-radius: 4px; cursor: pointer; font-weight: bold;">
                    Save Changes
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

async function saveClusterChanges(clusterId, modalElement) {
    /**
     * Save edited cluster information.
     */
    const name = document.getElementById('editClusterName').value.trim();
    const skillLevel = document.getElementById('editClusterSkillLevel').value;

    if (!name) {
        showToast('Cluster name cannot be empty', 'error');
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/clusters/${clusterId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                name: name,
                skill_level: skillLevel
            })
        });

        if (res.ok) {
            showToast('Cluster updated successfully!', 'success');
            modalElement.remove();
            loadClusters(); // Refresh cluster list
        } else {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
        }
    } catch (e) {
        showToast('Update failed: ' + e.message, 'error');
    }
}

// =============================================================================
// SEARCH (FULL CONTENT)
// =============================================================================

async function searchKnowledge() {
    const query = document.getElementById('searchQuery').value;

    if (!query.trim()) {
        showToast('Enter a search query', 'error');
        return;
    }

    // Build query with optional filters
    const params = new URLSearchParams({
        q: query,
        top_k: '20'
    });
    // Add full_content as true (not string 'true')
    params.append('full_content', true);

    // Add optional filters if they exist in the UI
    const sourceTypeFilter = document.getElementById('filterSourceType')?.value;
    if (sourceTypeFilter) params.append('source_type', sourceTypeFilter);

    const skillLevelFilter = document.getElementById('filterSkillLevel')?.value;
    if (skillLevelFilter) params.append('skill_level', skillLevelFilter);

    const dateFromFilter = document.getElementById('filterDateFrom')?.value;
    if (dateFromFilter) params.append('date_from', dateFromFilter);

    const dateToFilter = document.getElementById('filterDateTo')?.value;
    if (dateToFilter) params.append('date_to', dateToFilter);

    const clusterFilter = document.getElementById('filterClusterId')?.value;
    if (clusterFilter) params.append('cluster_id', clusterFilter);

    try {
        const res = await fetch(
            `${API_BASE}/search_full?${params.toString()}`,
            {headers: {'Authorization': `Bearer ${token}`}}
        );

        if (res.ok) {
            const data = await res.json();
            displaySearchResults(data.results, query);
        }
    } catch (e) {
        showToast('Search failed', 'error');
    }
}

function clearSearchFilters() {
    /**
     * Clear all search filter values.
     */
    const filterIds = ['filterSourceType', 'filterSkillLevel', 'filterDateFrom', 'filterDateTo', 'filterClusterId'];
    filterIds.forEach(id => {
        const element = document.getElementById(id);
        if (element) element.value = '';
    });
    showToast('Filters cleared', 'info');
}

function displaySearchResults(results, searchQuery = '') {
    const area = document.getElementById('resultsArea');

    if (results.length === 0) {
        area.innerHTML = '<p style="color: #666;">No results found</p>';
        return;
    }

    area.innerHTML = `<h3>Search Results (${results.length})</h3>` +
        results.map(r => `
            <div class="search-result">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <strong>Doc ${r.doc_id}</strong>
                    <div style="display: flex; gap: 8px;">
                        <span style="color: #888;">Score: ${r.score.toFixed(3)}</span>
                        <button class="icon-btn" onclick="editDocumentMetadata(${r.doc_id})" title="Edit Document" style="background: none; border: none; cursor: pointer; font-size: 1.2rem;">✏️</button>
                        <button class="icon-btn" onclick="showTagMenuForDocument(${r.doc_id})" title="Add Tag" style="background: none; border: none; cursor: pointer; font-size: 1.2rem;">🏷️</button>
                        <button class="icon-btn" onclick="deleteDocument(${r.doc_id})" title="Delete" style="background: none; border: none; cursor: pointer; font-size: 1.2rem;">🗑️</button>
                    </div>
                </div>
                <p style="font-size: 0.9rem; color: #aaa; margin: 5px 0;">
                    ${r.metadata.source_type} •
                    Cluster: ${r.cluster?.name || 'None'} •
                    ${r.metadata.skill_level}
                </p>
                <div id="doc-tags-${r.doc_id}" class="document-tags" style="margin: 8px 0;">
                    <!-- Tags will be loaded here -->
                </div>
                <div class="concepts-list">
                    ${r.metadata.concepts.slice(0, 5).map(c =>
                        `<span class="concept-tag">${c.name}</span>`
                    ).join('')}
                </div>
                <details open style="margin-top: 10px;">
                    <summary>View Full Content (${r.content.length} chars)</summary>
                    <pre>${highlightSearchTerms(escapeHtml(r.content), searchQuery)}</pre>
                </details>
            </div>
        `).join('');

    // Load tags for each document
    results.forEach(r => {
        loadDocumentTags(r.doc_id);
    });
}

function highlightSearchTerms(text, query) {
    if (!query || !text) return text;
    const terms = query.toLowerCase().split(/\s+/).filter(t => t.length > 2);
    if (terms.length === 0) return text;

    let highlighted = text;
    terms.forEach(term => {
        const regex = new RegExp(`(${escapeRegex(term)})`, 'gi');
        highlighted = highlighted.replace(regex, '<mark style="background: #ffaa00; padding: 2px;">$1</mark>');
    });
    return highlighted;
}

function escapeRegex(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

async function deleteDocument(docId) {
    if (!confirm(`Delete document ${docId}? This cannot be undone.`)) {
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/documents/${docId}`, {
            method: 'DELETE',
            headers: {'Authorization': `Bearer ${token}`}
        });

        if (res.ok) {
            showToast(`Document ${docId} deleted`, 'success');
            const query = document.getElementById('searchQuery').value;
            if (query.trim()) {
                searchKnowledge();
            } else {
                loadClusters();
            }
        } else {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
        }
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
}

async function editDocumentMetadata(docId) {
    /**
     * Edit document metadata (topic, skill level, cluster).
     * Uses existing PUT /documents/{id}/metadata endpoint.
     */
    try {
        // First, get current document data
        const getRes = await fetch(`${API_BASE}/documents/${docId}`, {
            headers: {'Authorization': `Bearer ${token}`}
        });

        if (!getRes.ok) {
            showToast('Failed to load document', 'error');
            return;
        }

        const docData = await getRes.json();

        // Get list of clusters for dropdown
        const clustersRes = await fetch(`${API_BASE}/clusters`, {
            headers: {'Authorization': `Bearer ${token}`}
        });
        const {clusters} = await clustersRes.json();

        // Show modal with form
        const modal = document.createElement('div');
        modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 1000;';
        modal.innerHTML = `
            <div style="background: #1e1e2e; padding: 30px; border-radius: 12px; max-width: 500px; width: 90%;">
                <h3 style="margin-top: 0;">Edit Document ${docId}</h3>

                <label style="display: block; margin-top: 15px;">
                    Primary Topic:
                    <input type="text" id="editTopic" value="${docData.metadata.primary_topic || ''}"
                           style="width: 100%; margin-top: 5px; padding: 8px; background: #2a2a3e; border: 1px solid #444; color: #fff; border-radius: 4px;">
                </label>

                <label style="display: block; margin-top: 15px;">
                    Skill Level:
                    <select id="editSkillLevel" style="width: 100%; margin-top: 5px; padding: 8px; background: #2a2a3e; border: 1px solid #444; color: #fff; border-radius: 4px;">
                        <option value="beginner" ${docData.metadata.skill_level === 'beginner' ? 'selected' : ''}>Beginner</option>
                        <option value="intermediate" ${docData.metadata.skill_level === 'intermediate' ? 'selected' : ''}>Intermediate</option>
                        <option value="advanced" ${docData.metadata.skill_level === 'advanced' ? 'selected' : ''}>Advanced</option>
                    </select>
                </label>

                <label style="display: block; margin-top: 15px;">
                    Cluster:
                    <select id="editCluster" style="width: 100%; margin-top: 5px; padding: 8px; background: #2a2a3e; border: 1px solid #444; color: #fff; border-radius: 4px;">
                        ${clusters.map(c =>
                            `<option value="${c.id}" ${c.id === docData.metadata.cluster_id ? 'selected' : ''}>${c.name}</option>`
                        ).join('')}
                    </select>
                </label>

                <div style="display: flex; gap: 10px; margin-top: 25px; justify-content: flex-end;">
                    <button onclick="this.closest('div').parentElement.parentElement.remove()"
                            style="padding: 10px 20px; background: #555; border: none; color: #fff; border-radius: 4px; cursor: pointer;">
                        Cancel
                    </button>
                    <button onclick="saveDocumentMetadata(${docId}, this.closest('div').parentElement.parentElement)"
                            style="padding: 10px 20px; background: #00d4ff; border: none; color: #000; border-radius: 4px; cursor: pointer; font-weight: bold;">
                        Save Changes
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

    } catch (e) {
        showToast('Error loading document: ' + e.message, 'error');
    }
}

async function saveDocumentMetadata(docId, modalElement) {
    /**
     * Save edited document metadata.
     */
    const topic = document.getElementById('editTopic').value.trim();
    const skillLevel = document.getElementById('editSkillLevel').value;
    const clusterId = parseInt(document.getElementById('editCluster').value);

    try {
        const res = await fetch(`${API_BASE}/documents/${docId}/metadata`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                primary_topic: topic,
                skill_level: skillLevel,
                cluster_id: clusterId
            })
        });

        if (res.ok) {
            showToast('Document updated successfully!', 'success');
            modalElement.remove();

            // Refresh current view
            const query = document.getElementById('searchQuery').value;
            if (query.trim()) {
                searchKnowledge();
            } else {
                loadClusters();
            }
        } else {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
        }
    } catch (e) {
        showToast('Update failed: ' + e.message, 'error');
    }
}

// =============================================================================
// BUILD SUGGESTIONS
// =============================================================================

async function whatCanIBuild(event) {
    const button = event ? event.target : null;

    if (button) setButtonLoading(button, true);

    try {
        // Get quality filter toggle state
        const qualityFilterToggle = document.getElementById('qualityFilterToggle');
        const enableQualityFilter = qualityFilterToggle ? qualityFilterToggle.checked : true;

        // Get max suggestions from input field
        const maxSuggestionsInput = document.getElementById('maxSuggestionsInput');
        let maxSuggestions = maxSuggestionsInput ? parseInt(maxSuggestionsInput.value) : 5;

        // Validate and constrain
        if (isNaN(maxSuggestions) || maxSuggestions < 1) {
            maxSuggestions = 5;
        }
        if (maxSuggestions > 20) {
            maxSuggestions = 20;
        }

        const res = await fetch(`${API_BASE}/what_can_i_build`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                max_suggestions: maxSuggestions,
                enable_quality_filter: enableQualityFilter
            })
        });

        if (res.ok) {
            const data = await res.json();
            displayBuildSuggestions(data.suggestions, data.knowledge_summary);
        } else {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    } finally {
        if (button) setButtonLoading(button, false, 'What Can I Build?');
    }
}

function displayBuildSuggestions(suggestions, summary) {
    const area = document.getElementById('resultsArea');
    const qualityFilterToggle = document.getElementById('qualityFilterToggle');
    const filterEnabled = qualityFilterToggle ? qualityFilterToggle.checked : true;

    if (suggestions.length === 0) {
        area.innerHTML = `
            <p style="color: #666;">
                Not enough knowledge yet to suggest builds.
                Upload more content (${summary.total_docs} docs so far).
            </p>
        `;
        return;
    }

    area.innerHTML = `
        <h3>💡 Build Suggestions</h3>
        <p style="color: #aaa; margin-bottom: 10px;">
            Based on ${summary.total_docs} documents across ${summary.total_clusters} clusters
        </p>
        <p style="color: #777; font-size: 0.9rem; margin-bottom: 20px;">
            ${filterEnabled
                ? '✅ Quality filter enabled - Showing ' + suggestions.length + ' high-quality suggestion' + (suggestions.length !== 1 ? 's' : '')
                : '📋 All suggestions shown (' + suggestions.length + ' total)'
            }
        </p>
    ` + suggestions.map((s, i) => `
        <div class="build-suggestion feasibility-${s.feasibility}">
            <h3>${i + 1}. ${s.title}</h3>
            <p style="margin: 10px 0;">${s.description}</p>

            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 15px 0;">
                <div>
                    <strong>Feasibility:</strong>
                    <span class="concept-tag">${s.feasibility}</span>
                </div>
                <div>
                    <strong>Effort:</strong> ${s.effort_estimate}
                </div>
                <div>
                    <strong>Level:</strong>
                    <span class="concept-tag">${s.complexity_level || 'intermediate'}</span>
                </div>
            </div>

            <div style="margin: 15px 0;">
                <strong>Required Skills:</strong>
                <div class="concepts-list">
                    ${s.required_skills.map(skill =>
                        `<span class="concept-tag">${skill}</span>`
                    ).join('')}
                </div>
            </div>

            ${s.missing_knowledge && s.missing_knowledge.length > 0 ? `
                <div style="margin: 15px 0;">
                    <strong style="color: #ffaa00;">⚠️ Missing Knowledge:</strong>
                    <ul style="margin-left: 20px; color: #aaa;">
                        ${s.missing_knowledge.map(gap => `<li>${gap}</li>`).join('')}
                    </ul>
                </div>
            ` : ''}

            ${s.expected_outcomes && s.expected_outcomes.length > 0 ? `
                <div style="margin: 15px 0;">
                    <strong style="color: #00ff88;">🎯 Expected Outcomes:</strong>
                    <ul style="margin-left: 20px; color: #aaa;">
                        ${s.expected_outcomes.map(outcome => `<li>${outcome}</li>`).join('')}
                    </ul>
                </div>
            ` : ''}

            <details style="margin-top: 15px;">
                <summary style="cursor: pointer; color: #00d4ff; font-weight: 600;">
                    📋 View Implementation Details
                </summary>
                <div style="background: #111; padding: 15px; border-radius: 4px; margin-top: 10px;">
                    <h4>🚀 First Steps:</h4>
                    <ol style="margin-left: 20px; color: #ddd;">
                        ${s.starter_steps.map(step => `<li style="margin: 8px 0;">${step}</li>`).join('')}
                    </ol>

                    ${s.file_structure ? `
                        <h4 style="margin-top: 20px;">📁 File Structure:</h4>
                        <pre style="background: #0a0a0a; padding: 10px; border-radius: 4px; color: #ddd;">${s.file_structure}</pre>
                    ` : ''}

                    ${s.starter_code ? `
                        <h4 style="margin-top: 20px;">💻 Starter Code:</h4>
                        <pre style="background: #0a0a0a; padding: 10px; border-radius: 4px; overflow-x: auto; color: #ddd;">${s.starter_code}</pre>
                    ` : ''}
                </div>
            </details>

            ${s.learning_path && s.learning_path.length > 0 ? `
                <details style="margin-top: 15px;">
                    <summary style="cursor: pointer; color: #ff9500; font-weight: 600;">
                        📚 Learning Path
                    </summary>
                    <div style="background: #111; padding: 15px; border-radius: 4px; margin-top: 10px;">
                        <ol style="margin-left: 20px; color: #ddd;">
                            ${s.learning_path.map(step => `<li style="margin: 8px 0;">${step}</li>`).join('')}
                        </ol>
                    </div>
                </details>
            ` : ''}

            ${s.recommended_resources && s.recommended_resources.length > 0 ? `
                <details style="margin-top: 15px;">
                    <summary style="cursor: pointer; color: #00d4ff; font-weight: 600;">
                        🔗 Recommended Resources
                    </summary>
                    <div style="background: #111; padding: 15px; border-radius: 4px; margin-top: 10px;">
                        <ul style="margin-left: 20px; color: #ddd;">
                            ${s.recommended_resources.map(resource => `<li style="margin: 8px 0;">${resource}</li>`).join('')}
                        </ul>
                    </div>
                </details>
            ` : ''}

            ${s.troubleshooting_tips && s.troubleshooting_tips.length > 0 ? `
                <details style="margin-top: 15px;">
                    <summary style="cursor: pointer; color: #ff4444; font-weight: 600;">
                        🔧 Troubleshooting Tips
                    </summary>
                    <div style="background: #111; padding: 15px; border-radius: 4px; margin-top: 10px;">
                        <ul style="margin-left: 20px; color: #ddd;">
                            ${s.troubleshooting_tips.map(tip => `<li style="margin: 8px 0;">${tip}</li>`).join('')}
                        </ul>
                    </div>
                </details>
            ` : ''}
        </div>
    `).join('');
}

// =============================================================================
// AI GENERATION (RAG)
// =============================================================================

function showAIGenerator() {
    const panel = document.getElementById('aiGeneratorPanel');
    panel.classList.remove('hidden');
    document.getElementById('aiPrompt').focus();
}

function hideAIGenerator() {
    const panel = document.getElementById('aiGeneratorPanel');
    panel.classList.add('hidden');
    document.getElementById('aiResponseArea').style.display = 'none';
    document.getElementById('aiPrompt').value = '';
    document.getElementById('aiResponse').textContent = '';
}

async function generateWithAI(event) {
    const button = event ? event.target : null;
    const prompt = document.getElementById('aiPrompt').value.trim();
    const model = document.getElementById('aiModelSelect').value;

    if (!prompt) {
        showToast('Please enter a prompt', 'error');
        return;
    }

    if (button) setButtonLoading(button, true);

    try {
        const res = await fetch(`${API_BASE}/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ prompt, model })
        });

        if (res.ok) {
            const data = await res.json();
            displayAIResponse(data.response);
        } else {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
        }
    } catch (e) {
        showToast('AI Generation error: ' + e.message, 'error');
    } finally {
        if (button) setButtonLoading(button, false, 'Generate');
    }
}

function displayAIResponse(response) {
    const responseArea = document.getElementById('aiResponseArea');
    const responseDiv = document.getElementById('aiResponse');

    responseDiv.textContent = response;
    responseArea.style.display = 'block';

    showToast('AI response generated successfully', 'success');
}

// =============================================================================
// HELPERS
// =============================================================================

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    
    if (type === 'error') {
        toast.style.borderLeftColor = '#ff4444';
    } else if (type === 'info') {
        toast.style.borderLeftColor = '#ffaa00';
    }
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// =============================================================================
// DEBOUNCING
// =============================================================================

let searchDebounceTimeout;

function debounceSearch() {
    /**
     * Debounce search input to avoid excessive API calls.
     * Waits 300ms after user stops typing before triggering search.
     */
    clearTimeout(searchDebounceTimeout);
    searchDebounceTimeout = setTimeout(() => {
        const query = document.getElementById('searchQuery').value;
        if (query.trim()) {
            searchKnowledge();
        }
    }, 300);
}

// =============================================================================
// EXPORT FUNCTIONALITY (Phase 4)
// =============================================================================

async function exportCluster(clusterId, format = 'json') {
    try {
        const res = await fetch(`${API_BASE}/export/cluster/${clusterId}?format=${format}`, {
            headers: {'Authorization': `Bearer ${token}`}
        });

        if (!res.ok) {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
            return;
        }

        const data = await res.json();

        // Download file
        if (format === 'markdown') {
            downloadFile(data.content, `cluster_${clusterId}_${data.cluster_name}.md`, 'text/markdown');
        } else {
            downloadFile(JSON.stringify(data, null, 2), `cluster_${clusterId}.json`, 'application/json');
        }

        showToast(`Cluster exported as ${format.toUpperCase()}`, 'success');
    } catch (e) {
        showToast('Export failed: ' + e.message, 'error');
    }
}

async function deleteCluster(clusterId, clusterName) {
    // Show custom dialog with options
    const choice = await showDeleteClusterDialog(clusterName);

    if (choice === 'cancel') {
        return;
    }

    const deleteDocuments = (choice === 'delete_all');

    try {
        const res = await fetch(`${API_BASE}/clusters/${clusterId}?delete_documents=${deleteDocuments}`, {
            method: 'DELETE',
            headers: {'Authorization': `Bearer ${token}`}
        });

        if (!res.ok) {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
            return;
        }

        const data = await res.json();

        if (deleteDocuments) {
            showToast(`💥 Cluster "${clusterName}" and ${data.documents_deleted} documents DELETED permanently!`, 'success');
        } else {
            showToast(`Cluster "${clusterName}" deleted. ${data.documents_unclustered} documents unclustered.`, 'success');
        }

        // Reload clusters list
        await loadClusters();
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
}

function showDeleteClusterDialog(clusterName) {
    return new Promise((resolve) => {
        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
        `;

        // Create modal
        const modal = document.createElement('div');
        modal.style.cssText = `
            background: white;
            border-radius: 8px;
            padding: 24px;
            max-width: 500px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        `;

        modal.innerHTML = `
            <h3 style="margin: 0 0 16px 0; color: #333;">Delete Cluster "${clusterName}"?</h3>
            <p style="margin: 0 0 20px 0; color: #666;">Choose how to delete this cluster:</p>

            <label style="display: block; padding: 12px; border: 2px solid #ddd; border-radius: 4px; margin-bottom: 12px; cursor: pointer;">
                <input type="radio" name="deleteOption" value="cluster_only" checked style="margin-right: 8px;">
                <strong>Remove cluster only</strong> (keep documents)
                <div style="margin-left: 24px; margin-top: 4px; font-size: 0.9em; color: #666;">
                    Documents stay in your knowledge base, just unclustered. You can search and use them.
                </div>
            </label>

            <label style="display: block; padding: 12px; border: 2px solid #ff4444; border-radius: 4px; margin-bottom: 20px; cursor: pointer;">
                <input type="radio" name="deleteOption" value="delete_all" style="margin-right: 8px;">
                <strong style="color: #ff4444;">Delete cluster + ALL documents (PERMANENT)</strong>
                <div style="margin-left: 24px; margin-top: 4px; font-size: 0.9em; color: #666;">
                    ⚠️ Removes cluster AND deletes all documents inside it forever. Cannot be undone!
                </div>
            </label>

            <div style="display: flex; gap: 10px; justify-content: flex-end;">
                <button id="cancelBtn" style="padding: 8px 16px; background: #ddd; border: none; border-radius: 4px; cursor: pointer;">Cancel</button>
                <button id="deleteBtn" style="padding: 8px 16px; background: #ff4444; color: white; border: none; border-radius: 4px; cursor: pointer;">Delete</button>
            </div>
        `;

        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        // Handle cancel
        modal.querySelector('#cancelBtn').onclick = () => {
            document.body.removeChild(overlay);
            resolve('cancel');
        };

        // Handle delete
        modal.querySelector('#deleteBtn').onclick = () => {
            const selectedOption = modal.querySelector('input[name="deleteOption"]:checked').value;
            document.body.removeChild(overlay);
            resolve(selectedOption);
        };

        // Close on overlay click
        overlay.onclick = (e) => {
            if (e.target === overlay) {
                document.body.removeChild(overlay);
                resolve('cancel');
            }
        };
    });
}

async function exportAll(format = 'json') {
    if (!confirm(`Export entire knowledge bank as ${format.toUpperCase()}?`)) {
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/export/all?format=${format}`, {
            headers: {'Authorization': `Bearer ${token}`}
        });

        if (!res.ok) {
            const errorMsg = await getErrorMessage(res);
            showToast(errorMsg, 'error');
            return;
        }

        const data = await res.json();

        // Download file
        const timestamp = new Date().toISOString().split('T')[0];
        if (format === 'markdown') {
            downloadFile(data.content, `knowledge_bank_${timestamp}.md`, 'text/markdown');
        } else {
            downloadFile(JSON.stringify(data, null, 2), `knowledge_bank_${timestamp}.json`, 'application/json');
        }

        showToast('Full export complete!', 'success');
    } catch (e) {
        showToast('Export failed: ' + e.message, 'error');
    }
}

function downloadFile(content, filename, contentType) {
    const blob = new Blob([content], { type: contentType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// =============================================================================
// KEYBOARD SHORTCUTS (Phase 4)
// =============================================================================

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+K or Cmd+K: Focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.getElementById('searchQuery');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }

        // Esc: Clear search or close modals
        if (e.key === 'Escape') {
            const searchInput = document.getElementById('searchQuery');
            if (searchInput && searchInput.value) {
                searchInput.value = '';
                document.getElementById('resultsArea').innerHTML = '';
            }
        }

        // N: Scroll to top (for new upload)
        if (e.key === 'n' && !e.ctrlKey && !e.metaKey && !e.altKey) {
            // Only if not in an input field
            if (document.activeElement.tagName !== 'INPUT' &&
                document.activeElement.tagName !== 'TEXTAREA') {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        }
    });

    console.log('⌨️  Keyboard shortcuts enabled: Ctrl+K (search), Esc (clear), N (scroll to top)');
}

// =============================================================================
// INIT
// =============================================================================

// Check if already logged in
const savedToken = localStorage.getItem('token');
if (savedToken) {
    token = savedToken;
    document.getElementById('authSection').classList.add('hidden');
    document.getElementById('mainContent').classList.remove('hidden');
    toggleLogoutButton(true);
    loadClusters();
}

// Set up search input debouncing and keyboard shortcuts
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('searchQuery');
    if (searchInput) {
        searchInput.addEventListener('input', debounceSearch);
    }

    // Enable keyboard shortcuts (Phase 4)
    setupKeyboardShortcuts();
});

// =============================================================================
// Analytics Dashboard (Phase 7.1)
// =============================================================================

const analyticsCharts = {
    timeSeries: null,
    cluster: null,
    skillLevel: null,
    sourceType: null
};

// Tab switching
function showTab(tabName) {
    // Update tab buttons
    document.getElementById('searchTab').classList.remove('active');
    document.getElementById('analyticsTab').classList.remove('active');
    document.getElementById('integrationsTab').classList.remove('active');
    document.getElementById('advancedTab').classList.remove('active');

    // Update content visibility
    document.getElementById('searchContent').classList.add('hidden');
    document.getElementById('analyticsContent').classList.add('hidden');
    document.getElementById('integrationsContent').classList.add('hidden');
    document.getElementById('advancedContent').classList.add('hidden');

    if (tabName === 'search') {
        document.getElementById('searchTab').classList.add('active');
        document.getElementById('searchContent').classList.remove('hidden');
    } else if (tabName === 'analytics') {
        document.getElementById('analyticsTab').classList.add('active');
        document.getElementById('analyticsContent').classList.remove('hidden');
        // Load analytics when tab is shown
        loadAnalytics();
    } else if (tabName === 'integrations') {
        document.getElementById('integrationsTab').classList.add('active');
        document.getElementById('integrationsContent').classList.remove('hidden');
        // Load integrations when tab is shown
        loadIntegrationStatus();
    } else if (tabName === 'advanced') {
        document.getElementById('advancedTab').classList.add('active');
        document.getElementById('advancedContent').classList.remove('hidden');
        // Load data for advanced features
        loadTags();
        loadSavedSearches();
    }
}

// Load analytics data
async function loadAnalytics() {
    const timePeriod = document.getElementById('timePeriodSelect').value;

    try {
        const response = await fetch(`${API_BASE}/analytics?time_period=${timePeriod}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error('Failed to load analytics');
        }

        const data = await response.json();

        // Render all analytics sections
        renderOverviewStats(data.overview);
        renderTimeSeriesChart(data.time_series);
        renderClusterChart(data.cluster_distribution);
        renderSkillLevelChart(data.skill_level_distribution);
        renderSourceTypeChart(data.source_type_distribution);
        renderTopConcepts(data.top_concepts);
        renderRecentActivity(data.recent_activity);

    } catch (error) {
        console.error('Analytics error:', error);
        alert('Failed to load analytics: ' + error.message);
    }
}

function resetAnalyticsCanvas(canvasId) {
    const oldCanvas = document.getElementById(canvasId);
    if (!oldCanvas || !oldCanvas.parentNode) {
        return oldCanvas || null;
    }
    const newCanvas = oldCanvas.cloneNode(true);
    oldCanvas.parentNode.replaceChild(newCanvas, oldCanvas);
    return newCanvas;
}

function showChartPlaceholder(canvasId, message) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !canvas.parentElement) {
        return;
    }
    let placeholder = canvas.parentElement.querySelector(`.chart-placeholder[data-for="${canvasId}"]`);
    if (!placeholder) {
        placeholder = document.createElement('div');
        placeholder.className = 'chart-placeholder';
        placeholder.dataset.for = canvasId;
        canvas.parentElement.appendChild(placeholder);
    }
    placeholder.textContent = message;
    placeholder.classList.remove('hidden');
    canvas.classList.add('hidden');
}

function hideChartPlaceholder(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
        return;
    }
    const placeholder = canvas.parentElement
        ? canvas.parentElement.querySelector(`.chart-placeholder[data-for="${canvasId}"]`)
        : null;
    if (placeholder) {
        placeholder.classList.add('hidden');
    }
    canvas.classList.remove('hidden');
}

// Render overview statistics
function renderOverviewStats(overview) {
    const container = document.getElementById('overviewStats');

    container.innerHTML = `
        <div class="stat-card">
            <h4>Total Documents</h4>
            <div class="stat-value">${overview.total_documents}</div>
            <div class="stat-change">+${overview.documents_today} today</div>
        </div>
        <div class="stat-card">
            <h4>Total Clusters</h4>
            <div class="stat-value">${overview.total_clusters}</div>
        </div>
        <div class="stat-card">
            <h4>Total Concepts</h4>
            <div class="stat-value">${overview.total_concepts}</div>
        </div>
        <div class="stat-card">
            <h4>This Week</h4>
            <div class="stat-value">${overview.documents_this_week}</div>
            <div class="stat-change">Documents added</div>
        </div>
        <div class="stat-card">
            <h4>This Month</h4>
            <div class="stat-value">${overview.documents_this_month}</div>
            <div class="stat-change">Documents added</div>
        </div>
    `;
}

// Render time series chart
function renderTimeSeriesChart(timeSeriesData) {
    if (!timeSeriesData || !timeSeriesData.labels || timeSeriesData.labels.length === 0) {
        showChartPlaceholder('timeSeriesChart', 'No document activity yet.');
        return;
    }
    hideChartPlaceholder('timeSeriesChart');

    // Destroy existing chart if it exists
    if (analyticsCharts.timeSeries) {
        analyticsCharts.timeSeries.destroy();
    }

    const canvas = resetAnalyticsCanvas('timeSeriesChart');
    if (!canvas) {
        return;
    }

    try {
        analyticsCharts.timeSeries = new Chart(canvas, {
            type: 'line',
            data: {
                labels: timeSeriesData.labels,
                datasets: [{
                    label: 'Documents Added',
                    data: timeSeriesData.data,
                    borderColor: '#00d4ff',
                    backgroundColor: 'rgba(0, 212, 255, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: '#e0e0e0'
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#888' },
                        grid: { color: '#333' }
                    },
                    y: {
                        ticks: { color: '#888' },
                        grid: { color: '#333' },
                        beginAtZero: true
                    }
                }
            }
        });
        canvas.style.height = '300px';
    } catch (error) {
        console.error('Time series chart error:', error);
        showChartPlaceholder('timeSeriesChart', 'Unable to render document growth chart.');
    }

}

// Render cluster distribution chart
function renderClusterChart(clusterData) {
    if (!clusterData || !clusterData.labels || clusterData.labels.length === 0) {
        showChartPlaceholder('clusterChart', 'No clusters available yet.');
        return;
    }
    hideChartPlaceholder('clusterChart');

    if (analyticsCharts.cluster) {
        analyticsCharts.cluster.destroy();
    }

    const canvas = resetAnalyticsCanvas('clusterChart');
    if (!canvas) {
        return;
    }

    try {
        analyticsCharts.cluster = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: clusterData.labels,
                datasets: [{
                    label: 'Documents',
                    data: clusterData.data,
                    backgroundColor: '#00d4ff',
                    borderColor: '#00a8cc',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: '#e0e0e0' }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#888' },
                        grid: { color: '#333' }
                    },
                    y: {
                        ticks: { color: '#888' },
                        grid: { color: '#333' },
                        beginAtZero: true
                    }
                }
            }
        });
        canvas.style.height = '250px';
    } catch (error) {
        console.error('Cluster chart error:', error);
        showChartPlaceholder('clusterChart', 'Unable to render cluster distribution chart.');
    }
}

// Render skill level distribution chart
function renderSkillLevelChart(skillLevelData) {
    if (!skillLevelData || !skillLevelData.labels || skillLevelData.labels.length === 0) {
        showChartPlaceholder('skillLevelChart', 'Skill data will appear after onboarding documents.');
        return;
    }
    hideChartPlaceholder('skillLevelChart');

    if (analyticsCharts.skillLevel) {
        analyticsCharts.skillLevel.destroy();
    }

    const canvas = resetAnalyticsCanvas('skillLevelChart');
    if (!canvas) {
        return;
    }

    try {
        analyticsCharts.skillLevel = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: skillLevelData.labels,
                datasets: [{
                    data: skillLevelData.data,
                    backgroundColor: [
                        '#00d4ff',
                        '#4ade80',
                        '#f59e0b',
                        '#ef4444'
                    ],
                    borderWidth: 2,
                    borderColor: '#1a1a1a'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#e0e0e0' }
                    }
                }
            }
        });
        canvas.style.height = '250px';
    } catch (error) {
        console.error('Skill level chart error:', error);
        showChartPlaceholder('skillLevelChart', 'Unable to render skill distribution chart.');
    }
}

// Render source type distribution chart
function renderSourceTypeChart(sourceTypeData) {
    if (!sourceTypeData || !sourceTypeData.labels || sourceTypeData.labels.length === 0) {
        showChartPlaceholder('sourceTypeChart', 'Upload content to see source distribution.');
        return;
    }
    hideChartPlaceholder('sourceTypeChart');

    if (analyticsCharts.sourceType) {
        analyticsCharts.sourceType.destroy();
    }

    const canvas = resetAnalyticsCanvas('sourceTypeChart');
    if (!canvas) {
        return;
    }

    try {
        analyticsCharts.sourceType = new Chart(canvas, {
            type: 'pie',
            data: {
                labels: sourceTypeData.labels,
                datasets: [{
                    data: sourceTypeData.data,
                    backgroundColor: [
                        '#00d4ff',
                        '#4ade80',
                        '#f59e0b',
                        '#ef4444',
                        '#8b5cf6'
                    ],
                    borderWidth: 2,
                    borderColor: '#1a1a1a'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#e0e0e0' }
                    }
                }
            }
        });
        canvas.style.height = '250px';
    } catch (error) {
        console.error('Source type chart error:', error);
        showChartPlaceholder('sourceTypeChart', 'Unable to render source distribution chart.');
    }
}

// Render top concepts list
function renderTopConcepts(topConcepts) {
    const container = document.getElementById('topConceptsList');

    if (topConcepts.length === 0) {
        container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">No concepts found</p>';
        return;
    }

    container.innerHTML = topConcepts.map(concept => `
        <div class="concept-item">
            <span class="concept-text">${concept.concept}</span>
            <span class="concept-count">${concept.count}</span>
        </div>
    `).join('');
}

// Render recent activity
function renderRecentActivity(recentActivity) {
    const container = document.getElementById('recentActivity');

    if (recentActivity.length === 0) {
        container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">No recent activity</p>';
        return;
    }

    container.innerHTML = recentActivity.map(activity => {
        const date = new Date(activity.created_at);
        const timeAgo = getTimeAgo(date);

        return `
            <div class="activity-item">
                <div class="activity-info">
                    <div class="activity-type">${activity.source_type || 'Document'}</div>
                    <div class="activity-details">
                        Skill Level: ${activity.skill_level || 'Unknown'} •
                        Cluster ID: ${activity.cluster_id !== null ? activity.cluster_id : 'None'}
                    </div>
                </div>
                <div class="activity-time">${timeAgo}</div>
            </div>
        `;
    }).join('');
}

// Helper function to format time ago
function getTimeAgo(date) {
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
    return date.toLocaleDateString();
}

// =============================================================================
// Advanced Features (Phase 7.2-7.5)
// =============================================================================

// Switch between advanced feature sub-tabs
function showAdvancedFeature(featureName) {
    // Update sub-tab buttons
    const subTabs = ['duplicatesSubTab', 'tagsSubTab', 'savedSearchesSubTab', 'relationshipsSubTab'];
    subTabs.forEach(tabId => {
        document.getElementById(tabId).classList.remove('active');
    });

    // Hide all feature sections
    const sections = ['duplicatesFeature', 'tagsFeature', 'savedSearchesFeature', 'relationshipsFeature'];
    sections.forEach(sectionId => {
        document.getElementById(sectionId).classList.add('hidden');
    });

    // Show selected feature
    if (featureName === 'duplicates') {
        document.getElementById('duplicatesSubTab').classList.add('active');
        document.getElementById('duplicatesFeature').classList.remove('hidden');
    } else if (featureName === 'tags') {
        document.getElementById('tagsSubTab').classList.add('active');
        document.getElementById('tagsFeature').classList.remove('hidden');
        loadTags();
    } else if (featureName === 'savedSearches') {
        document.getElementById('savedSearchesSubTab').classList.add('active');
        document.getElementById('savedSearchesFeature').classList.remove('hidden');
        loadSavedSearches();
    } else if (featureName === 'relationships') {
        document.getElementById('relationshipsSubTab').classList.add('active');
        document.getElementById('relationshipsFeature').classList.remove('hidden');
    }
}

// =============================================================================
// Phase 7.2: Duplicate Detection
// =============================================================================

async function findDuplicates() {
    const threshold = document.getElementById('duplicateThreshold').value;
    const resultsDiv = document.getElementById('duplicatesResults');

    resultsDiv.innerHTML = '<p style="color: #888;">Searching for duplicates...</p>';

    try {
        const response = await fetch(`${API_BASE}/duplicates?threshold=${threshold}&limit=100`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            return;
        }

        const data = await response.json();
        renderDuplicateGroups(data.duplicate_groups);

    } catch (error) {
        showToast('Failed to find duplicates: ' + error.message, 'error');
        resultsDiv.innerHTML = '<p style="color: #ff4444;">Error loading duplicates</p>';
    }
}

function renderDuplicateGroups(groups) {
    const resultsDiv = document.getElementById('duplicatesResults');

    if (groups.length === 0) {
        resultsDiv.innerHTML = '<p style="color: #888; padding: 20px;">No duplicate groups found at this threshold.</p>';
        return;
    }

    // Helper function to get document display title
    function getDocTitle(doc) {
        // Prioritize extracted title (from YouTube, articles, etc.)
        if (doc.title) {
            return doc.title.length > 60 ? doc.title.substring(0, 57) + '...' : doc.title;
        }

        // Fall back to filename
        if (doc.filename) {
            return doc.filename.length > 50 ? doc.filename.substring(0, 47) + '...' : doc.filename;
        }

        // Fall back to URL
        if (doc.source_url) {
            try {
                const url = new URL(doc.source_url);
                let title = url.hostname.replace('www.', '');
                if (url.pathname !== '/' && url.pathname !== '') {
                    const path = url.pathname.split('/').filter(p => p).slice(-1)[0];
                    title += '/' + (path.length > 30 ? path.substring(0, 27) + '...' : path);
                }
                return title;
            } catch {
                return doc.source_url.length > 50 ? doc.source_url.substring(0, 47) + '...' : doc.source_url;
            }
        }

        // Final fallback
        return `Doc ${doc.doc_id}`;
    }

    resultsDiv.innerHTML = `
        <h3>Found ${groups.length} Duplicate Groups</h3>
        ${groups.map((group, idx) => {
            const allDocs = [group.primary_doc, ...group.duplicates];
            const avgSimilarity = group.duplicates.length > 0
                ? group.duplicates.reduce((sum, d) => sum + d.similarity, 0) / group.duplicates.length
                : 1.0;
            return `
            <div class="duplicate-group">
                <h4>Group ${idx + 1} (${group.group_size} documents, ${(avgSimilarity * 100).toFixed(1)}% similar)</h4>
                ${allDocs.map((doc, docIdx) => `
                    <div class="duplicate-doc" style="background: #1a1a1a; padding: 10px; margin: 8px 0; border-radius: 4px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div style="flex: 1; min-width: 0;">
                                <strong style="color: ${docIdx === 0 ? '#4ade80' : '#fff'};">${docIdx === 0 ? '👑 ' : ''}${escapeHtml(getDocTitle(doc))}</strong>
                                <div style="font-size: 0.85rem; color: #666; margin-top: 4px;">
                                    ID: ${doc.doc_id} • ${doc.source_type || 'N/A'}
                                </div>
                            </div>
                            <div style="text-align: right; white-space: nowrap; margin-left: 10px;">
                                <span style="color: #888; font-size: 0.85rem;">${doc.similarity !== undefined ? (doc.similarity * 100).toFixed(1) + '% similar' : 'Primary'}</span>
                            </div>
                        </div>
                    </div>
                `).join('')}
                <div style="margin-top: 10px; display: flex; gap: 10px;">
                    ${group.group_size === 2 ?
                        `<button onclick="compareDuplicates(${group.primary_doc.doc_id}, ${group.duplicates[0].doc_id})" style="background: #00d4ff; color: #000; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer;">
                            📊 Compare Side-by-Side
                        </button>` : ''}
                    <button onclick="mergeDuplicateGroup(${idx}, ${JSON.stringify([group.primary_doc.doc_id, ...group.duplicates.map(d => d.doc_id)])})" style="background: #f59e0b; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer;">
                        Merge Group (Keep First, Delete Others)
                    </button>
                </div>
            </div>
        `}).join('')}
    `;
}

async function mergeDuplicateGroup(groupIdx, docIds) {
    const keepId = docIds[0];
    const deleteIds = docIds.slice(1);

    if (!confirm(`Keep document ${keepId} and delete ${deleteIds.length} duplicate(s)?\n\nThis cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/duplicates/merge`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                keep_doc_id: keepId,
                delete_doc_ids: deleteIds
            })
        });

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            return;
        }

        showToast(`Merged successfully! Kept doc ${keepId}, deleted ${deleteIds.length} duplicate(s)`, 'success');

        // Refresh duplicate search
        findDuplicates();

    } catch (error) {
        showToast('Failed to merge duplicates: ' + error.message, 'error');
    }
}

async function compareDuplicates(docId1, docId2) {
    /**
     * Show side-by-side comparison of two duplicate documents.
     * Uses existing GET /duplicates/{id1}/{id2} endpoint.
     */
    try {
        const response = await fetch(`${API_BASE}/duplicates/${docId1}/${docId2}`, {
            headers: {'Authorization': `Bearer ${token}`}
        });

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            return;
        }

        const data = await response.json();

        // Helper function to get document display title (reused from renderDuplicateGroups)
        function getDocTitle(doc) {
            // Prioritize extracted title (from YouTube, articles, etc.)
            if (doc.title) {
                return doc.title.length > 60 ? doc.title.substring(0, 57) + '...' : doc.title;
            }

            // Fall back to filename
            if (doc.filename) {
                return doc.filename.length > 50 ? doc.filename.substring(0, 47) + '...' : doc.filename;
            }

            // Fall back to URL
            if (doc.source_url) {
                try {
                    const url = new URL(doc.source_url);
                    let title = url.hostname.replace('www.', '');
                    if (url.pathname !== '/' && url.pathname !== '') {
                        const path = url.pathname.split('/').filter(p => p).slice(-1)[0];
                        title += '/' + (path.length > 30 ? path.substring(0, 27) + '...' : path);
                    }
                    return title;
                } catch {
                    return doc.source_url.length > 50 ? doc.source_url.substring(0, 47) + '...' : doc.source_url;
                }
            }

            // Final fallback
            return `Doc ${doc.doc_id}`;
        }

        // Show comparison modal
        const modal = document.createElement('div');
        modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 20px; overflow: auto;';
        modal.innerHTML = `
            <div style="background: #1e1e2e; padding: 30px; border-radius: 12px; max-width: 1200px; width: 100%; max-height: 90vh; overflow-y: auto;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h3 style="margin: 0;">Duplicate Comparison</h3>
                    <button onclick="this.closest('div').parentElement.parentElement.remove()" style="background: #555; border: none; color: #fff; padding: 8px 16px; border-radius: 4px; cursor: pointer;">
                        Close
                    </button>
                </div>

                <div style="background: #2a2a3e; padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: center;">
                    <h4 style="margin: 0 0 5px 0; color: #00d4ff;">Similarity Score: ${(data.similarity * 100).toFixed(1)}%</h4>
                    <p style="margin: 0; color: #888; font-size: 0.9rem;">Higher score = more similar content</p>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <!-- Document 1 -->
                    <div>
                        <h4 style="margin-top: 0; color: #4ade80;">👑 ${escapeHtml(getDocTitle(data.doc1))}</h4>
                        <div style="font-size: 0.85rem; color: #888; margin-bottom: 10px;">Document ID: ${docId1}</div>
                        <div style="background: #1a1a1a; padding: 10px; border-radius: 4px; margin-bottom: 10px;">
                            <div style="font-size: 0.85rem; color: #888;">
                                <strong>Type:</strong> ${data.doc1.source_type || 'N/A'}<br>
                                <strong>Skill Level:</strong> ${data.doc1.skill_level || 'N/A'}<br>
                                <strong>Cluster:</strong> ${data.doc1.cluster_id !== null ? data.doc1.cluster_id : 'None'}<br>
                                <strong>Length:</strong> ${data.doc1.content.length} chars
                            </div>
                        </div>
                        <div style="background: #0a0a0a; padding: 15px; border-radius: 4px; max-height: 400px; overflow-y: auto;">
                            <pre style="white-space: pre-wrap; margin: 0; font-size: 0.85rem;">${escapeHtml(data.doc1.content)}</pre>
                        </div>
                    </div>

                    <!-- Document 2 -->
                    <div>
                        <h4 style="margin-top: 0; color: #f59e0b;">${escapeHtml(getDocTitle(data.doc2))}</h4>
                        <div style="font-size: 0.85rem; color: #888; margin-bottom: 10px;">Document ID: ${docId2}</div>
                        <div style="background: #1a1a1a; padding: 10px; border-radius: 4px; margin-bottom: 10px;">
                            <div style="font-size: 0.85rem; color: #888;">
                                <strong>Type:</strong> ${data.doc2.source_type || 'N/A'}<br>
                                <strong>Skill Level:</strong> ${data.doc2.skill_level || 'N/A'}<br>
                                <strong>Cluster:</strong> ${data.doc2.cluster_id !== null ? data.doc2.cluster_id : 'None'}<br>
                                <strong>Length:</strong> ${data.doc2.content.length} chars
                            </div>
                        </div>
                        <div style="background: #0a0a0a; padding: 15px; border-radius: 4px; max-height: 400px; overflow-y: auto;">
                            <pre style="white-space: pre-wrap; margin: 0; font-size: 0.85rem;">${escapeHtml(data.doc2.content)}</pre>
                        </div>
                    </div>
                </div>

                <div style="margin-top: 20px; text-align: center;">
                    <button onclick="this.closest('div').parentElement.parentElement.remove(); mergeDuplicateGroup(0, [${docId1}, ${docId2}])"
                            style="background: #f59e0b; border: none; color: #fff; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold;">
                        Merge (Keep Doc ${docId1}, Delete Doc ${docId2})
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

    } catch (error) {
        showToast('Failed to load comparison: ' + error.message, 'error');
    }
}

// =============================================================================
// Phase 7.3: Tags System
// =============================================================================

async function createTag() {
    const name = document.getElementById('newTagName').value.trim();
    const color = document.getElementById('newTagColor').value;

    if (!name) {
        showToast('Tag name cannot be empty', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/tags`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ name, color })
        });

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            return;
        }

        showToast(`Tag "${name}" created successfully`, 'success');

        // Clear input and reload
        document.getElementById('newTagName').value = '';
        loadTags();

    } catch (error) {
        showToast('Failed to create tag: ' + error.message, 'error');
    }
}

async function loadTags() {
    try {
        const response = await fetch(`${API_BASE}/tags`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            console.error('Failed to load tags');
            return;
        }

        const data = await response.json();
        renderTags(data.tags);

    } catch (error) {
        console.error('Failed to load tags:', error);
    }
}

function renderTags(tags) {
    const container = document.getElementById('tagsListContainer');

    if (tags.length === 0) {
        container.innerHTML = '<p style="color: #888; padding: 20px;">No tags yet. Create one above!</p>';
        return;
    }

    container.innerHTML = `
        <h3>Your Tags (${tags.length})</h3>
        <div style="display: grid; gap: 10px; margin-top: 15px;">
            ${tags.map(tag => `
                <div class="tag-item" style="background: #1a1a1a; padding: 12px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="width: 20px; height: 20px; background: ${tag.color}; border-radius: 4px; display: inline-block;"></span>
                        <strong>${tag.name}</strong>
                        <span style="color: #888; font-size: 0.9rem;">(${tag.document_count} docs)</span>
                    </div>
                    <button onclick="deleteTag(${tag.id}, '${tag.name}')" style="background: #ff4444; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer;">Delete</button>
                </div>
            `).join('')}
        </div>
    `;
}

async function deleteTag(tagId, tagName) {
    if (!confirm(`Delete tag "${tagName}"? This will remove it from all documents.`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/tags/${tagId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            return;
        }

        showToast(`Tag "${tagName}" deleted`, 'success');
        loadTags();

    } catch (error) {
        showToast('Failed to delete tag: ' + error.message, 'error');
    }
}

// =============================================================================
// Document Tagging Functions
// =============================================================================

async function loadDocumentTags(docId) {
    try {
        const response = await fetch(`${API_BASE}/documents/${docId}/tags`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            console.error('Failed to load document tags');
            return;
        }

        const data = await response.json();
        renderDocumentTags(docId, data.tags || []);

    } catch (error) {
        console.error('Failed to load document tags:', error);
    }
}

function renderDocumentTags(docId, tags) {
    const container = document.getElementById(`doc-tags-${docId}`);
    if (!container) return;

    if (tags.length === 0) {
        container.innerHTML = '<span style="color: #666; font-size: 0.85rem;">No tags</span>';
        return;
    }

    container.innerHTML = tags.map(tag => `
        <span class="tag-badge" style="background: ${tag.color || '#00d4ff'}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.85rem; margin-right: 5px; display: inline-flex; align-items: center; gap: 5px;">
            ${tag.name}
            <button onclick="removeTagFromDocument(${docId}, ${tag.id}, '${tag.name}')" style="background: none; border: none; color: white; cursor: pointer; font-size: 1rem; padding: 0; line-height: 1;">×</button>
        </span>
    `).join('');
}

async function showTagMenuForDocument(docId) {
    try {
        const response = await fetch(`${API_BASE}/tags`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            showToast('Failed to load tags', 'error');
            return;
        }

        const data = await response.json();
        const tags = data.tags || [];

        if (tags.length === 0) {
            showToast('No tags available. Create tags first in the Advanced tab.', 'info');
            return;
        }

        // Create simple menu with available tags
        const tagOptions = tags.map(tag => `${tag.id}: ${tag.name}`).join('\n');
        const tagIdStr = prompt(`Select tag to add to document ${docId}:\n\n${tagOptions}\n\nEnter tag ID:`);

        if (tagIdStr) {
            const tagId = parseInt(tagIdStr);
            if (isNaN(tagId)) {
                showToast('Invalid tag ID', 'error');
                return;
            }

            await addTagToDocument(docId, tagId);
        }

    } catch (error) {
        showToast('Failed to show tag menu: ' + error.message, 'error');
    }
}

async function addTagToDocument(docId, tagId) {
    try {
        const response = await fetch(`${API_BASE}/documents/${docId}/tags/${tagId}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            return;
        }

        showToast('Tag added to document', 'success');
        loadDocumentTags(docId);

    } catch (error) {
        showToast('Failed to add tag: ' + error.message, 'error');
    }
}

async function removeTagFromDocument(docId, tagId, tagName) {
    if (!confirm(`Remove tag "${tagName}" from document ${docId}?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/documents/${docId}/tags/${tagId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            return;
        }

        showToast('Tag removed from document', 'success');
        loadDocumentTags(docId);

    } catch (error) {
        showToast('Failed to remove tag: ' + error.message, 'error');
    }
}

// =============================================================================
// Phase 7.4: Saved Searches
// =============================================================================

async function saveCurrentSearch() {
    const query = document.getElementById('searchQuery').value.trim();
    const name = prompt('Enter a name for this search:');

    if (!name) return;

    if (!query) {
        showToast('No search query to save', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/saved-searches`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                name,
                query,
                filters: {}
            })
        });

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            return;
        }

        showToast(`Search "${name}" saved successfully`, 'success');
        loadSavedSearches();

    } catch (error) {
        showToast('Failed to save search: ' + error.message, 'error');
    }
}

async function loadSavedSearches() {
    try {
        const response = await fetch(`${API_BASE}/saved-searches`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            console.error('Failed to load saved searches');
            return;
        }

        const data = await response.json();
        renderSavedSearches(data.saved_searches);

    } catch (error) {
        console.error('Failed to load saved searches:', error);
    }
}

function renderSavedSearches(searches) {
    const container = document.getElementById('savedSearchesListContainer');

    if (searches.length === 0) {
        container.innerHTML = '<p style="color: #888; padding: 20px;">No saved searches yet. Save your frequent searches for quick access!</p>';
        return;
    }

    container.innerHTML = `
        <h3>Saved Searches (${searches.length})</h3>
        <div style="display: grid; gap: 10px; margin-top: 15px;">
            ${searches.map(search => `
                <div class="saved-search-item" style="background: #1a1a1a; padding: 12px; border-radius: 6px;">
                    <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 8px;">
                        <strong style="color: #00d4ff; flex-grow: 1; cursor: pointer;" onclick="useSavedSearch(${search.id})">${search.name}</strong>
                        <button onclick="deleteSavedSearch(${search.id}, '${search.name}')" style="background: #ff4444; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">Delete</button>
                    </div>
                    <div style="color: #888; font-size: 0.9rem; margin-bottom: 4px;">
                        Query: "${search.query}"
                    </div>
                    <div style="color: #666; font-size: 0.85rem;">
                        Used ${search.use_count} times
                        ${search.last_used_at ? ' • Last used ' + getTimeAgo(new Date(search.last_used_at)) : ''}
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

async function useSavedSearch(searchId) {
    try {
        const response = await fetch(`${API_BASE}/saved-searches/${searchId}/use`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            return;
        }

        const data = await response.json();

        // Switch to search tab and execute the search
        showTab('search');
        document.getElementById('searchQuery').value = data.query;
        searchKnowledge();

    } catch (error) {
        showToast('Failed to use saved search: ' + error.message, 'error');
    }
}

async function deleteSavedSearch(searchId, searchName) {
    if (!confirm(`Delete saved search "${searchName}"?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/saved-searches/${searchId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            return;
        }

        showToast(`Saved search "${searchName}" deleted`, 'success');
        loadSavedSearches();

    } catch (error) {
        showToast('Failed to delete saved search: ' + error.message, 'error');
    }
}

// =============================================================================
// Phase 7.5: Document Relationships
// =============================================================================

async function createRelationship() {
    const sourceDocId = parseInt(document.getElementById('relationshipSourceDoc').value);
    const targetDocId = parseInt(document.getElementById('relationshipTargetDoc').value);
    const relationType = document.getElementById('relationshipType').value;

    if (!sourceDocId || !targetDocId) {
        showToast('Please enter both document IDs', 'error');
        return;
    }

    if (sourceDocId === targetDocId) {
        showToast('Source and target must be different documents', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/documents/${sourceDocId}/relationships`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                target_doc_id: targetDocId,
                relationship_type: relationType
            })
        });

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            return;
        }

        showToast(`Relationship created: ${sourceDocId} → ${targetDocId} (${relationType})`, 'success');

        // Clear inputs
        document.getElementById('relationshipSourceDoc').value = '';
        document.getElementById('relationshipTargetDoc').value = '';

    } catch (error) {
        showToast('Failed to create relationship: ' + error.message, 'error');
    }
}

async function viewDocumentRelationships() {
    const docId = parseInt(document.getElementById('viewRelationshipsDocId').value);

    if (!docId) {
        showToast('Please enter a document ID', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/documents/${docId}/relationships`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            return;
        }

        const data = await response.json();
        renderDocumentRelationships(docId, data.relationships);

    } catch (error) {
        showToast('Failed to load relationships: ' + error.message, 'error');
    }
}

function renderDocumentRelationships(docId, relationships) {
    const container = document.getElementById('relationshipsResultsContainer');

    if (relationships.length === 0) {
        container.innerHTML = `<p style="color: #888; padding: 20px;">Document ${docId} has no relationships.</p>`;
        return;
    }

    const relationshipColors = {
        'related': '#00d4ff',
        'prerequisite': '#4ade80',
        'followup': '#f59e0b',
        'alternative': '#8b5cf6',
        'supersedes': '#ef4444'
    };

    container.innerHTML = `
        <h3>Relationships for Document ${docId} (${relationships.length})</h3>
        <div style="display: grid; gap: 10px; margin-top: 15px;">
            ${relationships.map(rel => `
                <div style="background: #1a1a1a; padding: 12px; border-radius: 6px; border-left: 4px solid ${relationshipColors[rel.relationship_type] || '#666'};">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong>Doc ${rel.doc_id}</strong>
                            <span class="relationship-type-badge" style="background: ${relationshipColors[rel.relationship_type] || '#666'}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; margin-left: 8px;">
                                ${rel.relationship_type}
                            </span>
                            <span style="color: #888; margin-left: 8px; font-size: 0.9rem;">
                                (${rel.direction})
                            </span>
                        </div>
                        <button onclick="deleteRelationship(${docId}, ${rel.doc_id})" style="background: #ff4444; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">Remove</button>
                    </div>
                    <div style="color: #888; font-size: 0.9rem; margin-top: 6px;">
                        ${rel.source_type} • ${rel.skill_level} • Cluster: ${rel.cluster_id !== null ? rel.cluster_id : 'None'}
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

async function deleteRelationship(sourceDocId, targetDocId) {
    if (!confirm(`Delete relationship between documents ${sourceDocId} and ${targetDocId}?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/documents/${sourceDocId}/relationships/${targetDocId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            return;
        }

        showToast('Relationship deleted', 'success');

        // Refresh the view
        viewDocumentRelationships();

    } catch (error) {
        showToast('Failed to delete relationship: ' + error.message, 'error');
    }
}

/**
 * Discover Related Documents (AI Auto-Discovery)
 * Uses vector search to find documents similar to the specified document.
 */
async function discoverRelatedDocuments() {
    const docId = parseInt(document.getElementById('discoverRelatedDocId').value);
    const topK = parseInt(document.getElementById('discoveryTopK').value) || 5;
    const minSimilarity = parseFloat(document.getElementById('discoveryMinSimilarity').value) || 0.1;

    if (!docId) {
        showToast('Please enter a document ID to discover related documents', 'error');
        return;
    }

    const resultsDiv = document.getElementById('discoveredDocumentsResults');
    resultsDiv.innerHTML = '<p style="color: #888;">🔍 Discovering related documents...</p>';

    try {
        const response = await fetch(
            `${API_BASE}/documents/${docId}/discover-related?top_k=${topK}&min_similarity=${minSimilarity}`,
            {
                headers: { 'Authorization': `Bearer ${token}` }
            }
        );

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            resultsDiv.innerHTML = `<p style="color: #ff4444;">Error: ${errorMsg}</p>`;
            return;
        }

        const data = await response.json();
        renderDiscoveredDocuments(docId, data.related_documents);

        showToast(`Found ${data.count} related documents`, 'success');

    } catch (error) {
        showToast('Failed to discover related documents: ' + error.message, 'error');
        resultsDiv.innerHTML = `<p style="color: #ff4444;">Error: ${error.message}</p>`;
    }
}

/**
 * Render discovered related documents with similarity scores
 */
function renderDiscoveredDocuments(sourceDocId, relatedDocs) {
    const container = document.getElementById('discoveredDocumentsResults');

    if (relatedDocs.length === 0) {
        container.innerHTML = `
            <p style="color: #888; padding: 20px; background: #1a1a1a; border-radius: 6px;">
                No related documents found. Try lowering the similarity threshold.
            </p>
        `;
        return;
    }

    container.innerHTML = `
        <h4 style="color: #00ff88; margin-bottom: 15px;">
            🎯 Found ${relatedDocs.length} Related Documents for Doc ${sourceDocId}
        </h4>
        <div style="display: grid; gap: 12px;">
            ${relatedDocs.map(doc => {
                const similarityPercent = (doc.similarity_score * 100).toFixed(1);
                const similarityColor = doc.similarity_score > 0.5 ? '#00ff88' :
                                       doc.similarity_score > 0.3 ? '#ffaa00' : '#888';

                return `
                    <div style="background: #1a1a1a; padding: 15px; border-radius: 6px; border-left: 4px solid ${similarityColor};">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                            <div style="flex: 1;">
                                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                                    <strong style="color: #e0e0e0; font-size: 1.1rem;">Doc ${doc.doc_id}</strong>
                                    <span style="background: ${similarityColor}; color: #000; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 0.85rem;">
                                        ${similarityPercent}% similar
                                    </span>
                                </div>
                                <div style="color: #888; font-size: 0.9rem;">
                                    📄 ${doc.source_type} •
                                    🎯 ${doc.skill_level || 'N/A'} •
                                    📁 Cluster ${doc.cluster_id !== null ? doc.cluster_id : 'None'}
                                </div>
                                ${doc.filename ? `
                                    <div style="color: #666; font-size: 0.85rem; margin-top: 4px;">
                                        📎 ${doc.filename}
                                    </div>
                                ` : ''}
                                ${doc.source_url ? `
                                    <div style="color: #666; font-size: 0.85rem; margin-top: 4px; word-break: break-all;">
                                        🔗 ${doc.source_url}
                                    </div>
                                ` : ''}
                                <div style="color: #555; font-size: 0.8rem; margin-top: 4px;">
                                    Ingested: ${new Date(doc.ingested_at).toLocaleString()}
                                </div>
                            </div>
                            <button
                                onclick="quickLinkDocuments(${sourceDocId}, ${doc.doc_id})"
                                style="background: #00d4ff; color: #000; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.9rem; white-space: nowrap;"
                                title="Create a 'related' relationship">
                                🔗 Quick Link
                            </button>
                        </div>
                    </div>
                `;
            }).join('')}
        </div>
        <div style="margin-top: 15px; padding: 12px; background: #2a2a2a; border-radius: 6px; color: #888; font-size: 0.9rem;">
            💡 <strong>Tip:</strong> Use "Quick Link" to create a relationship, or manually specify the relationship type below.
        </div>
    `;
}

/**
 * Quick link two documents with a 'related' relationship
 */
async function quickLinkDocuments(sourceDocId, targetDocId) {
    try {
        const response = await fetch(`${API_BASE}/documents/${sourceDocId}/relationships`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                target_doc_id: targetDocId,
                relationship_type: 'related'
            })
        });

        if (!response.ok) {
            const errorMsg = await getErrorMessage(response);
            showToast(errorMsg, 'error');
            return;
        }

        showToast(`✅ Linked Doc ${sourceDocId} ↔ Doc ${targetDocId}`, 'success');

        // Auto-populate the view relationships input and show the results
        document.getElementById('viewRelationshipsDocId').value = sourceDocId;

        // Automatically fetch and display the relationships to show the user where it went
        const viewResponse = await fetch(`${API_BASE}/documents/${sourceDocId}/relationships`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (viewResponse.ok) {
            const data = await viewResponse.json();
            renderDocumentRelationships(sourceDocId, data.relationships);

            // Scroll to results so user can see them
            document.getElementById('relationshipsResultsContainer').scrollIntoView({
                behavior: 'smooth',
                block: 'nearest'
            });
        }

    } catch (error) {
        showToast('Failed to link documents: ' + error.message, 'error');
    }
}

// =============================================================================
// KEYBOARD SHORTCUTS
// =============================================================================

/**
 * Global keyboard shortcuts for power users.
 * 
 * Shortcuts:
 * - Ctrl/Cmd + K: Focus search input
 * - Ctrl/Cmd + U: Switch to upload tab
 * - Ctrl/Cmd + B: Trigger "What Can I Build?"
 * - Ctrl/Cmd + /: Show keyboard shortcuts help
 * - Escape: Close modals (handled by modal close buttons)
 */
document.addEventListener('keydown', (e) => {
    // Ctrl+K or Cmd+K: Focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('searchQuery');
        if (searchInput) {
            showTab('search');
            searchInput.focus();
            searchInput.select();
        }
    }

    // Ctrl+U or Cmd+U: Open upload tab
    if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
        e.preventDefault();
        showTab('upload');
    }

    // Ctrl+B or Cmd+B: What Can I Build?
    if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
        e.preventDefault();
        showTab('search');
        whatCanIBuild();
    }

    // Ctrl+/ or Cmd+/: Show keyboard shortcuts help
    if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault();
        showKeyboardShortcutsHelp();
    }
});

function showKeyboardShortcutsHelp() {
    /**
     * Display keyboard shortcuts help modal.
     */
    const modal = document.createElement('div');
    modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center; z-index: 1000;';
    modal.innerHTML = `
        <div style="background: #1e1e2e; padding: 30px; border-radius: 12px; max-width: 500px; width: 90%;">
            <h3 style="margin-top: 0; display: flex; justify-content: space-between; align-items: center;">
                ⌨️ Keyboard Shortcuts
                <button onclick="this.closest('div').parentElement.parentElement.remove()" style="background: #555; border: none; color: #fff; padding: 6px 12px; border-radius: 4px; cursor: pointer;">
                    Close
                </button>
            </h3>

            <div style="margin-top: 20px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div>
                        <div style="background: #2a2a3e; padding: 10px; border-radius: 6px; margin-bottom: 10px;">
                            <div style="font-weight: bold; color: #00d4ff; margin-bottom: 4px;">
                                <kbd style="background: #1a1a1a; padding: 4px 8px; border-radius: 4px;">Ctrl/Cmd</kbd> + <kbd style="background: #1a1a1a; padding: 4px 8px; border-radius: 4px;">K</kbd>
                            </div>
                            <div style="color: #aaa; font-size: 0.9rem;">Focus Search</div>
                        </div>
                        <div style="background: #2a2a3e; padding: 10px; border-radius: 6px; margin-bottom: 10px;">
                            <div style="font-weight: bold; color: #00d4ff; margin-bottom: 4px;">
                                <kbd style="background: #1a1a1a; padding: 4px 8px; border-radius: 4px;">Ctrl/Cmd</kbd> + <kbd style="background: #1a1a1a; padding: 4px 8px; border-radius: 4px;">U</kbd>
                            </div>
                            <div style="color: #aaa; font-size: 0.9rem;">Open Upload Tab</div>
                        </div>
                    </div>
                    <div>
                        <div style="background: #2a2a3e; padding: 10px; border-radius: 6px; margin-bottom: 10px;">
                            <div style="font-weight: bold; color: #00d4ff; margin-bottom: 4px;">
                                <kbd style="background: #1a1a1a; padding: 4px 8px; border-radius: 4px;">Ctrl/Cmd</kbd> + <kbd style="background: #1a1a1a; padding: 4px 8px; border-radius: 4px;">B</kbd>
                            </div>
                            <div style="color: #aaa; font-size: 0.9rem;">What Can I Build?</div>
                        </div>
                        <div style="background: #2a2a3e; padding: 10px; border-radius: 6px; margin-bottom: 10px;">
                            <div style="font-weight: bold; color: #00d4ff; margin-bottom: 4px;">
                                <kbd style="background: #1a1a1a; padding: 4px 8px; border-radius: 4px;">Ctrl/Cmd</kbd> + <kbd style="background: #1a1a1a; padding: 4px 8px; border-radius: 4px;">/</kbd>
                            </div>
                            <div style="color: #aaa; font-size: 0.9rem;">Show This Help</div>
                        </div>
                    </div>
                </div>
            </div>

            <div style="margin-top: 20px; padding: 12px; background: #2a2a3e; border-radius: 6px; border-left: 4px solid #00d4ff;">
                <div style="font-weight: bold; margin-bottom: 4px;">💡 Pro Tip</div>
                <div style="color: #aaa; font-size: 0.9rem;">
                    Press <kbd style="background: #1a1a1a; padding: 2px 6px; border-radius: 3px;">Esc</kbd> to close any modal dialog.
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    // Also allow Escape to close this modal
    modal.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            modal.remove();
        }
    });
}

// =============================================================================
// CELERY JOB POLLING
// =============================================================================

/**
 * Poll Celery job status for background tasks.
 *
 * @param {string} jobId - Celery task ID
 * @param {HTMLElement|null} button - Button to update with progress
 * @param {string} buttonDefaultText - Text to show when job completes
 */
async function pollJobStatus(jobId, button = null, buttonDefaultText = 'Done') {
    const pollInterval = 1000; // Poll every second
    const maxAttempts = 300; // Max 5 minutes of polling
    let attempts = 0;

    const interval = setInterval(async () => {
        attempts++;

        // Timeout after max attempts
        if (attempts > maxAttempts) {
            clearInterval(interval);
            showToast('⏱️ Job timeout - check back later', 'warning');
            if (button) setButtonLoading(button, false, buttonDefaultText);
            return;
        }

        try {
            const res = await fetch(`${API_BASE}/jobs/${jobId}/status`, {
                headers: {'Authorization': `Bearer ${token}`}
            });

            if (!res.ok) {
                clearInterval(interval);
                showToast('❌ Failed to check job status', 'error');
                if (button) setButtonLoading(button, false, buttonDefaultText);
                return;
            }

            const data = await res.json();
            const status = data.status;

            // Update button with progress
            if (button && (data.message || data.current_step)) {
                const message = data.current_step || data.message;
                const progressText = data.progress !== undefined
                    ? `${message} ${data.progress}%`
                    : message;
                setButtonText(button, progressText);
            }

            // Handle different states
            if (status === 'PENDING') {
                // Task waiting in queue
                if (button) setButtonText(button, '⏳ Queued...');
            }
            else if (status === 'PROCESSING') {
                // Task is running - progress shown above
                // Keep polling
            }
            else if (status === 'SUCCESS') {
                // Task completed successfully
                clearInterval(interval);
                if (button) setButtonLoading(button, false, buttonDefaultText);

                // Show success message
                if (data.document_id) {
                    showToast(
                        `✅ Uploaded! Doc ${data.document_id} → Cluster ${data.cluster_id}`,
                        'success'
                    );
                } else {
                    showToast('✅ Processing complete!', 'success');
                }

                // Refresh clusters
                loadClusters();
            }
            else if (status === 'FAILURE') {
                // Task failed
                clearInterval(interval);
                if (button) setButtonLoading(button, false, buttonDefaultText);

                const errorMsg = data.error || 'Unknown error';
                showToast(`❌ Processing failed: ${errorMsg}`, 'error');
            }
            else if (status === 'RETRY') {
                // Task is being retried
                if (button) setButtonText(button, '🔄 Retrying...');
            }
            else if (status === 'REVOKED') {
                // Task was cancelled
                clearInterval(interval);
                if (button) setButtonLoading(button, false, buttonDefaultText);
                showToast('🚫 Task cancelled', 'warning');
            }

        } catch (e) {
            console.error('Job polling error:', e);
            // Continue polling - might be transient network issue
        }
    }, pollInterval);
}

/**
 * Helper to update button text without changing loading state.
 *
 * @param {HTMLElement} button - Button element
 * @param {string} text - New text
 */
function setButtonText(button, text) {
    if (!button) return;
    button.textContent = text;
}

// =============================================================================
// CLOUD INTEGRATIONS (Phase 5)
// =============================================================================

/**
 * Load integration connection status for all services.
 * Displays service cards showing connected/disconnected state.
 */
async function loadIntegrationStatus() {
    try {
        const response = await fetch(`${API_BASE}/integrations/status`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) throw new Error('Failed to load integration status');

        const data = await response.json();
        displayIntegrationCards(data.connections);

    } catch (e) {
        console.error('Integration status error:', e);
        showToast('Failed to load integrations: ' + e.message, 'error');
    }
}

/**
 * Display integration service cards.
 * Shows connection status and actions for each service.
 */
function displayIntegrationCards(connections) {
    const container = document.getElementById('integrationCards');

    const services = {
        github: { icon: '🐙', name: 'GitHub', description: 'Import repositories and files' },
        google: { icon: '📁', name: 'Google Drive', description: 'Import documents and files' },
        dropbox: { icon: '📦', name: 'Dropbox', description: 'Import files and folders' },
        notion: { icon: '📝', name: 'Notion', description: 'Import pages and databases' }
    };

    container.innerHTML = '';

    for (const [service, info] of Object.entries(services)) {
        const connection = connections[service];
        const isConnected = connection.connected;

        const card = document.createElement('div');
        card.style.cssText = `
            background: #2a2a2a;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid ${isConnected ? '#00ff88' : '#666'};
        `;

        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 15px;">
                <div>
                    <div style="font-size: 2rem; margin-bottom: 5px;">${info.icon}</div>
                    <h3 style="margin: 0; color: #e0e0e0;">${info.name}</h3>
                </div>
                <span style="
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 0.85rem;
                    background: ${isConnected ? '#00ff8822' : '#66666622'};
                    color: ${isConnected ? '#00ff88' : '#888'};
                ">
                    ${isConnected ? '✓ Connected' : 'Not Connected'}
                </span>
            </div>

            <p style="color: #888; margin-bottom: 15px; font-size: 0.9rem;">${info.description}</p>

            ${isConnected ? `
                <div style="color: #888; font-size: 0.85rem; margin-bottom: 15px;">
                    <div><strong>User:</strong> ${connection.user || 'Unknown'}</div>
                    ${connection.email ? `<div><strong>Email:</strong> ${connection.email}</div>` : ''}
                    ${connection.last_sync ? `<div><strong>Last sync:</strong> ${formatDate(connection.last_sync)}</div>` : ''}
                </div>

                <div style="display: flex; gap: 10px;">
                    ${service === 'github' ? `
                        <button onclick="browseGitHub()" style="flex: 1;">Browse Repositories</button>
                    ` : `
                        <button style="flex: 1; opacity: 0.5;" disabled>Browse Files (Coming Soon)</button>
                    `}
                    <button onclick="disconnectService('${service}')" class="secondary">Disconnect</button>
                </div>
            ` : `
                <button onclick="connectService('${service}')" style="width: 100%;">Connect ${info.name}</button>
            `}
        `;

        container.appendChild(card);
    }
}

/**
 * Connect a cloud service via OAuth.
 * Opens OAuth flow in a new window.
 */
function connectService(service) {
    const authUrl = `${API_BASE}/integrations/${service}/authorize`;

    // Open OAuth in new window
    const width = 600;
    const height = 700;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;

    const authWindow = window.open(
        authUrl,
        `${service}_oauth`,
        `width=${width},height=${height},left=${left},top=${top}`
    );

    // Poll for window close (user completed OAuth)
    const pollTimer = setInterval(() => {
        if (authWindow.closed) {
            clearInterval(pollTimer);
            // Reload integration status
            setTimeout(() => loadIntegrationStatus(), 1000);
        }
    }, 500);
}

/**
 * Disconnect a cloud service.
 * Removes OAuth token from backend.
 */
async function disconnectService(service) {
    if (!confirm(`Disconnect ${service}? You'll need to reconnect to import files again.`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/integrations/${service}/disconnect`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) throw new Error('Failed to disconnect');

        showToast(`${service} disconnected successfully`, 'success');
        loadIntegrationStatus();

    } catch (e) {
        console.error('Disconnect error:', e);
        showToast('Failed to disconnect: ' + e.message, 'error');
    }
}

// =============================================================================
// GitHub Integration
// =============================================================================

let githubRepos = [];
let selectedGitHubFiles = [];
let currentRepo = null;
let currentPath = '';

/**
 * Browse GitHub repositories.
 * Opens modal showing user's repositories.
 */
async function browseGitHub() {
    try {
        const response = await fetch(`${API_BASE}/integrations/github/repos?per_page=50`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            if (response.status === 404) {
                showToast('GitHub not connected. Please connect first.', 'error');
                return;
            }
            throw new Error('Failed to load repositories');
        }

        const data = await response.json();
        githubRepos = data.repositories;

        showGitHubReposModal(githubRepos);

    } catch (e) {
        console.error('GitHub repos error:', e);
        showToast('Failed to load repositories: ' + e.message, 'error');
    }
}

/**
 * Show GitHub repositories modal.
 */
function showGitHubReposModal(repos) {
    const modal = document.createElement('div');
    modal.id = 'githubModal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.9);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        padding: 20px;
    `;

    modal.innerHTML = `
        <div style="
            background: #1a1a1a;
            border-radius: 12px;
            max-width: 800px;
            width: 100%;
            max-height: 90vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        ">
            <div style="padding: 20px; border-bottom: 2px solid #333;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h2 style="margin: 0;">🐙 GitHub Repositories</h2>
                    <button onclick="closeGitHubModal()" class="secondary">✕ Close</button>
                </div>
            </div>

            <div id="githubReposList" style="flex: 1; overflow-y: auto; padding: 20px;">
                ${repos.map(repo => `
                    <div style="
                        background: #2a2a2a;
                        padding: 15px;
                        border-radius: 8px;
                        margin-bottom: 15px;
                        border-left: 3px solid ${repo.private ? '#ff9900' : '#00d4ff'};
                    ">
                        <div style="display: flex; justify-content: space-between; align-items: start;">
                            <div style="flex: 1;">
                                <h3 style="margin: 0 0 5px 0;">${repo.name}</h3>
                                <p style="color: #888; font-size: 0.9rem; margin: 0 0 10px 0;">${repo.description || 'No description'}</p>
                                <div style="display: flex; gap: 15px; font-size: 0.85rem; color: #888;">
                                    <span>${repo.private ? '🔒 Private' : '🌐 Public'}</span>
                                    ${repo.language ? `<span>💻 ${repo.language}</span>` : ''}
                                    <span>⭐ ${repo.stargazers_count}</span>
                                    <span>📦 ${(repo.size / 1024).toFixed(1)} MB</span>
                                </div>
                            </div>
                            <button onclick='browseGitHubRepo(${JSON.stringify(repo)})' style="margin-left: 15px;">
                                Browse Files
                            </button>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;

    document.body.appendChild(modal);
}

/**
 * Browse files in a GitHub repository.
 */
async function browseGitHubRepo(repo) {
    currentRepo = repo;
    currentPath = '';
    selectedGitHubFiles = [];

    await loadGitHubRepoContents(repo.owner.login || repo.full_name.split('/')[0], repo.name, '');
}

/**
 * Load contents of a GitHub repository path.
 */
async function loadGitHubRepoContents(owner, repo, path) {
    try {
        const pathParam = path ? `?path=${encodeURIComponent(path)}` : '';
        const response = await fetch(
            `${API_BASE}/integrations/github/repos/${owner}/${repo}/contents${pathParam}`,
            { headers: { 'Authorization': `Bearer ${token}` } }
        );

        if (!response.ok) throw new Error('Failed to load repository contents');

        const data = await response.json();
        showGitHubFileBrowser(owner, repo, path, data.files);

    } catch (e) {
        console.error('GitHub contents error:', e);
        showToast('Failed to load repository contents: ' + e.message, 'error');
    }
}

/**
 * Show GitHub file browser modal.
 */
function showGitHubFileBrowser(owner, repo, path, files) {
    currentPath = path;

    const modal = document.getElementById('githubModal');
    if (!modal) return;

    const content = modal.querySelector('#githubReposList');
    if (!content) return;

    content.innerHTML = `
        <div style="margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <div>
                    <h3 style="margin: 0;">${owner}/${repo}</h3>
                    <p style="color: #888; font-size: 0.9rem; margin: 5px 0 0 0;">
                        Path: /${path || 'root'}
                    </p>
                </div>
                <div style="display: flex; gap: 10px;">
                    ${path ? `<button onclick="goUpDirectory('${owner}', '${repo}', '${path}')" class="secondary">⬆️ Up</button>` : ''}
                    <button onclick="browseGitHub()" class="secondary">⬅️ Back to Repos</button>
                </div>
            </div>

            <div style="margin-bottom: 15px; color: #888;">
                Selected: <strong>${selectedGitHubFiles.length}</strong> files
                ${selectedGitHubFiles.length > 0 ? `
                    <button onclick="importGitHubFiles('${owner}', '${repo}')" style="margin-left: 10px;">
                        Import Selected (${selectedGitHubFiles.length})
                    </button>
                ` : ''}
            </div>
        </div>

        <div>
            ${files.map(file => `
                <div style="
                    background: #2a2a2a;
                    padding: 12px 15px;
                    border-radius: 6px;
                    margin-bottom: 10px;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                ">
                    ${file.type === 'file' ? `
                        <input
                            type="checkbox"
                            id="file_${file.path.replace(/[^a-zA-Z0-9]/g, '_')}"
                            ${selectedGitHubFiles.includes(file.path) ? 'checked' : ''}
                            onchange="toggleFileSelection('${file.path}')"
                            style="width: 18px; height: 18px; cursor: pointer;"
                        >
                    ` : '<div style="width: 18px;"></div>'}

                    <div style="flex: 1; cursor: ${file.type === 'dir' ? 'pointer' : 'default'};"
                         onclick="${file.type === 'dir' ? `loadGitHubRepoContents('${owner}', '${repo}', '${file.path}')` : ''}">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 1.2rem;">${file.type === 'dir' ? '📁' : '📄'}</span>
                            <span>${file.name}</span>
                        </div>
                        ${file.type === 'file' ? `<div style="color: #666; font-size: 0.85rem;">${formatFileSize(file.size)}</div>` : ''}
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

/**
 * Go up one directory level.
 */
function goUpDirectory(owner, repo, currentPath) {
    const parts = currentPath.split('/');
    parts.pop();
    const newPath = parts.join('/');
    loadGitHubRepoContents(owner, repo, newPath);
}

/**
 * Toggle file selection for import.
 */
function toggleFileSelection(filePath) {
    const index = selectedGitHubFiles.indexOf(filePath);
    if (index === -1) {
        selectedGitHubFiles.push(filePath);
    } else {
        selectedGitHubFiles.splice(index, 1);
    }

    // Refresh the display to update selected count
    const owner = currentRepo.owner.login || currentRepo.full_name.split('/')[0];
    loadGitHubRepoContents(owner, currentRepo.name, currentPath);
}

/**
 * Import selected GitHub files.
 */
async function importGitHubFiles(owner, repo) {
    if (selectedGitHubFiles.length === 0) {
        showToast('No files selected', 'warning');
        return;
    }

    if (selectedGitHubFiles.length > 100) {
        showToast('Maximum 100 files per import', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/integrations/github/import`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                owner,
                repo,
                branch: currentRepo.default_branch || 'main',
                files: selectedGitHubFiles
            })
        });

        if (!response.ok) throw new Error('Failed to queue import');

        const data = await response.json();

        showToast(`📤 Import queued: ${data.file_count} files`, 'info');
        closeGitHubModal();

        // Poll for job status
        pollJobStatus(data.job_id, null, null);

    } catch (e) {
        console.error('GitHub import error:', e);
        showToast('Failed to import files: ' + e.message, 'error');
    }
}

/**
 * Close GitHub modal.
 */
function closeGitHubModal() {
    const modal = document.getElementById('githubModal');
    if (modal) {
        modal.remove();
    }
    selectedGitHubFiles = [];
    currentRepo = null;
    currentPath = '';
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Format file size in bytes to human-readable.
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
}

/**
 * Format date to relative time.
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    return date.toLocaleDateString();
}
