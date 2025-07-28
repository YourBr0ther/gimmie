let items = [];
let isOnline = navigator.onLine;
let retryAttempts = 0;
const MAX_RETRY_ATTEMPTS = 3;

// Enhanced logging function
function log(level, message, data = null) {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] ${level.toUpperCase()}: ${message}`;
    
    if (level === 'error') {
        console.error(logEntry, data || '');
    } else if (level === 'warn') {
        console.warn(logEntry, data || '');
    } else {
        console.log(logEntry, data || '');
    }
}

log('info', '🚀 Gimmie frontend initialized');

// Connection status monitoring
window.addEventListener('online', () => {
    isOnline = true;
    log('info', '🌐 Connection restored');
    showConnectionStatus('Connected', 'success');
    loadItems(); // Refresh data when back online
});

window.addEventListener('offline', () => {
    isOnline = false;
    log('warn', '📡 Connection lost');
    showConnectionStatus('Offline', 'warning');
});

function showConnectionStatus(message, type) {
    const existing = document.querySelector('.connection-status');
    if (existing) existing.remove();
    
    const status = document.createElement('div');
    status.className = `connection-status ${type}`;
    status.textContent = message;
    document.body.appendChild(status);
    
    setTimeout(() => {
        if (status.parentNode) status.remove();
    }, 3000);
}

async function apiCall(url, options = {}) {
    const maxRetries = 3;
    const retryDelay = 1000; // 1 second
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });
            
            if (!response.ok) {
                if (response.status >= 500 && attempt < maxRetries) {
                    // Server error, retry
                    await new Promise(resolve => setTimeout(resolve, retryDelay * attempt));
                    continue;
                } else if (response.status === 503) {
                    // Service unavailable
                    throw new Error('Service temporarily unavailable. Please try again.');
                } else {
                    // Other errors, don't retry
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || `HTTP ${response.status}`);
                }
            }
            
            return response;
        } catch (error) {
            if (attempt === maxRetries || error.name === 'TypeError') {
                // Network error or final attempt
                if (!isOnline) {
                    throw new Error('You are offline. Please check your connection.');
                }
                throw error;
            }
            
            // Wait before retry
            await new Promise(resolve => setTimeout(resolve, retryDelay * attempt));
        }
    }
}

async function loadItems() {
    log('info', '📋 Loading items from server');
    const itemsList = document.getElementById('items-list');
    itemsList.innerHTML = '<div class="loading">Loading...</div>';
    
    try {
        const response = await apiCall('/api/items');
        items = await response.json();
        log('info', `✅ Loaded ${items.length} items from server`);
        renderItems();
    } catch (error) {
        log('error', '❌ Failed to load items', error);
        itemsList.innerHTML = `
            <div class="error-message">
                <img src="/static/images/gimmie-sad-icon.png" alt="Connection Error" class="error-icon">
                <h3>Oops! Something went wrong</h3>
                <p>${error.message || 'Failed to load items'}</p>
                <button onclick="loadItems()" class="btn btn-small">Retry</button>
            </div>
        `;
    }
}

function renderItems() {
    const itemsList = document.getElementById('items-list');
    
    if (items.length === 0) {
        itemsList.innerHTML = `
            <div class="empty-state">
                <img src="/static/images/gimmie-sad-icon.png" alt="No Items" class="empty-icon">
                <h3>No items yet</h3>
                <p>Add your first item to get started!</p>
            </div>
        `;
        return;
    }
    
    itemsList.innerHTML = items.map((item, index) => `
        <div class="item-card" data-id="${item.id}">
            <div class="item-number">${index + 1}</div>
            <div class="item-content">
                <h3 class="item-name">${escapeHtml(item.name)}</h3>
                <div class="item-details">
                    ${item.cost ? `<span class="item-cost">$${item.cost.toFixed(2)}</span>` : ''}
                    <span class="item-type ${item.type}">${item.type}</span>
                    <span class="item-added-by">by ${escapeHtml(item.added_by)}</span>
                </div>
                ${item.link ? `<a href="${escapeHtml(item.link)}" target="_blank" rel="noopener noreferrer" class="item-link">View Link</a>` : ''}
            </div>
            <div class="item-actions">
                <button class="btn-icon" onclick="moveItem(${item.id}, 'up')" ${index === 0 ? 'disabled' : ''}>↑</button>
                <button class="btn-icon" onclick="moveItem(${item.id}, 'down')" ${index === items.length - 1 ? 'disabled' : ''}>↓</button>
                <button class="btn-icon btn-edit" onclick="editItem(${item.id})">✏</button>
                <button class="btn-icon btn-complete" onclick="completeItem(${item.id})">✓</button>
                <button class="btn-icon btn-delete" onclick="deleteItem(${item.id})">×</button>
            </div>
        </div>
    `).join('');
}

async function moveItem(id, direction) {
    try {
        await apiCall(`/api/items/${id}/move`, {
            method: 'POST',
            body: JSON.stringify({ direction })
        });
        await loadItems();
    } catch (error) {
        console.error('Error moving item:', error);
        showConnectionStatus(error.message || 'Failed to move item', 'error');
    }
}

async function completeItem(id) {
    if (confirm('Mark this item as completed?')) {
        try {
            await apiCall(`/api/items/${id}/complete`, { method: 'POST' });
            await loadItems();
        } catch (error) {
            console.error('Error completing item:', error);
            showConnectionStatus(error.message || 'Failed to complete item', 'error');
        }
    }
}

async function editItem(id) {
    const item = items.find(item => item.id === id);
    if (!item) return;
    
    // Pre-fill the form with existing data
    document.getElementById('item-name').value = item.name;
    document.getElementById('item-cost').value = item.cost || '';
    document.getElementById('item-link').value = item.link || '';
    document.getElementById('item-type').value = item.type;
    document.getElementById('item-added-by').value = item.added_by;
    
    // Change modal title and button text
    document.querySelector('#add-item-modal h2').textContent = 'Edit Item';
    document.querySelector('#add-item-form button[type="submit"]').textContent = 'Update Item';
    
    // Store the item ID for updating
    document.getElementById('add-item-form').dataset.editId = id;
    
    // Show the modal
    document.getElementById('add-item-modal').classList.add('show');
    document.getElementById('item-name').focus();
}

async function deleteItem(id) {
    if (confirm('Delete this item?')) {
        try {
            await apiCall(`/api/items/${id}`, { method: 'DELETE' });
            await loadItems();
        } catch (error) {
            console.error('Error deleting item:', error);
            showConnectionStatus(error.message || 'Failed to delete item', 'error');
        }
    }
}

async function restoreItem(archiveId) {
    if (confirm('Restore this item to your list?')) {
        try {
            await apiCall(`/api/archive/${archiveId}/restore`, { method: 'POST' });
            showConnectionStatus('Item restored to list', 'success');
            
            // Refresh both the main list and archive
            await loadItems();
            
            // Refresh archive modal if it's open
            const archiveModal = document.getElementById('archive-modal');
            if (archiveModal.classList.contains('show')) {
                // Re-trigger archive loading
                document.getElementById('archive-btn').click();
            }
        } catch (error) {
            console.error('Error restoring item:', error);
            showConnectionStatus(error.message || 'Failed to restore item', 'error');
        }
    }
}

function closeModal() {
    document.getElementById('add-item-modal').classList.remove('show');
    document.getElementById('add-item-form').reset();
    
    // Reset modal state
    document.querySelector('#add-item-modal h2').textContent = 'Add New Item';
    document.querySelector('#add-item-form button[type="submit"]').textContent = 'Add Item';
    delete document.getElementById('add-item-form').dataset.editId;
}

function closeArchiveModal() {
    document.getElementById('archive-modal').classList.remove('show');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

document.getElementById('add-item-btn').addEventListener('click', () => {
    document.getElementById('add-item-modal').classList.add('show');
    document.getElementById('item-name').focus();
});

document.getElementById('add-item-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const data = {
        name: formData.get('name'),
        cost: formData.get('cost') ? parseFloat(formData.get('cost')) : null,
        link: formData.get('link') || null,
        type: formData.get('type'),
        added_by: formData.get('added_by')
    };
    
    const editId = e.target.dataset.editId;
    
    try {
        if (editId) {
            // Update existing item
            await apiCall(`/api/items/${editId}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
        } else {
            // Create new item
            await apiCall('/api/items', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        }
        closeModal();
        await loadItems();
    } catch (error) {
        console.error('Error saving item:', error);
        showConnectionStatus(error.message || 'Failed to save item', 'error');
    }
});

document.getElementById('export-json-btn').addEventListener('click', () => {
    window.location.href = '/api/export?format=json';
});

document.getElementById('import-btn').addEventListener('click', () => {
    document.getElementById('import-file').click();
});

document.getElementById('import-file').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await apiCall('/api/import', {
            method: 'POST',
            body: formData,
            headers: {} // Let browser set Content-Type for FormData
        });
        
        const result = await response.json();
        showConnectionStatus(result.message || 'Import successful', 'success');
        await loadItems();
    } catch (error) {
        console.error('Error importing:', error);
        showConnectionStatus(error.message || 'Import failed', 'error');
    }
    
    e.target.value = '';
});

document.getElementById('archive-btn').addEventListener('click', async () => {
    try {
        const response = await apiCall('/api/archive');
        const archivedItems = await response.json();
        
        const archiveList = document.getElementById('archive-list');
        
        if (archivedItems.length === 0) {
            archiveList.innerHTML = `
                <div class="empty-state">
                    <img src="/static/images/gimmie-sad-icon.png" alt="No Archive" class="empty-icon">
                    <h3>No archived items</h3>
                    <p>Completed or deleted items will appear here</p>
                </div>
            `;
        } else {
            archiveList.innerHTML = archivedItems.map(item => `
                <div class="archive-item">
                    <div class="archive-item-header">
                        <h4>${escapeHtml(item.name)}</h4>
                        <div class="archive-header-actions">
                            <span class="archive-reason ${item.archived_reason}">${item.archived_reason}</span>
                            <button class="btn-icon btn-restore" onclick="restoreItem(${item.id})" title="Restore to list">↩</button>
                        </div>
                    </div>
                    <div class="archive-item-details">
                        ${item.cost ? `<span>$${item.cost.toFixed(2)}</span>` : ''}
                        <span class="item-type ${item.type}">${item.type}</span>
                        <span class="item-added-by">by ${escapeHtml(item.added_by || 'Unknown')}</span>
                        <span class="archive-date">${new Date(item.archived_at).toLocaleDateString()}</span>
                    </div>
                </div>
            `).join('');
        }
        
        document.getElementById('archive-modal').classList.add('show');
    } catch (error) {
        console.error('Error loading archive:', error);
        showConnectionStatus(error.message || 'Failed to load archive', 'error');
    }
});

window.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('show');
    }
});

// Periodic health check
let healthCheckInterval;

function startHealthCheck() {
    // Check connection every 30 seconds
    healthCheckInterval = setInterval(async () => {
        if (isOnline) {
            try {
                await apiCall('/api/items?health=1');
                // Connection is good, nothing to do
            } catch (error) {
                console.warn('Health check failed:', error);
                if (error.message.includes('offline') || error.message.includes('503')) {
                    // Show connection issue
                    showConnectionStatus('Connection issues detected', 'warning');
                }
            }
        }
    }, 30000);
}

function stopHealthCheck() {
    if (healthCheckInterval) {
        clearInterval(healthCheckInterval);
        healthCheckInterval = null;
    }
}

// Start the app
loadItems();
startHealthCheck();

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    stopHealthCheck();
});