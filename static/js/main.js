// 全域變數和工具函數
const API_BASE = window.location.origin;

// 防抖函數
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 標籤自動完成系統 - 增強版本
class TagAutocomplete {
    constructor(inputElement, onSelect, options = {}) {
        this.input = inputElement;
        this.onSelect = onSelect;
        this.dropdown = null;
        this.tags = [];
        this.selectedIndex = -1;
        this.categorySelector = options.categorySelector || null;
        this.autoPrefix = options.autoPrefix !== false; // 預設啟用自動前綴
        this.context = options.context || null; // 搜索上下文
        
        this.init();
    }
    
    init() {
        // 創建下拉選單
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'autocomplete-dropdown';
        this.dropdown.style.display = 'none';
        
        // 確保父元素存在並且有相對定位
        if (this.input.parentElement) {
            const parent = this.input.parentElement;
            if (getComputedStyle(parent).position === 'static') {
                parent.style.position = 'relative';
            }
            parent.appendChild(this.dropdown);
        } else {
            console.error("TagAutocomplete input element must have a parent.");
            return;
        }
        
        // 綁定事件
        this.input.addEventListener('input', debounce(() => this.search(), 300));
        this.input.addEventListener('keydown', (e) => this.handleKeydown(e));
        
        // 點擊外部隱藏下拉選單
        document.addEventListener('click', (e) => {
            if (this.dropdown && !this.input.contains(e.target) && !this.dropdown.contains(e.target)) {
                this.hide();
            }
        });
    }
    
    async search() {
        const query = this.input.value.trim();
        if (query.length < 1) {
            this.hide();
            return;
        }
        
        try {
            // 支持上下文感知搜索
            let url = `${API_BASE}/api/tags/search?q=${encodeURIComponent(query)}`;
            
            // 檢查是否有上下文信息
            if (this.context) {
                url += `&context=${encodeURIComponent(this.context)}`;
            }
            
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            this.tags = await response.json();
            this.render();
        } catch (error) {
            console.error('搜尋標籤失敗:', error);
            this.hide();
        }
    }
    
    render() {
        if (this.tags.length === 0) {
            this.hide();
            return;
        }
        
        this.dropdown.innerHTML = this.tags.map((tag, index) => `
            <div class="autocomplete-item ${index === this.selectedIndex ? 'selected' : ''}" 
                 data-index="${index}">
                <span class="badge" style="background-color: ${tag.color || '#6c757d'}">${tag.category || '其他'}</span>
                ${tag.name}
            </div>
        `).join('');
        
        // 綁定點擊事件
        this.dropdown.querySelectorAll('.autocomplete-item').forEach(item => {
            item.addEventListener('click', () => {
                const index = parseInt(item.dataset.index);
                this.select(index);
            });
        });
        
        this.show();
    }
    
    handleKeydown(e) {
        if (!this.dropdown || this.dropdown.style.display === 'none' || this.tags.length === 0) {
            return;
        }
        
        switch(e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedIndex = (this.selectedIndex + 1) % this.tags.length;
                this.render();
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.selectedIndex = (this.selectedIndex - 1 + this.tags.length) % this.tags.length;
                this.render();
                break;
            case 'Enter':
                // 只有在明確選中了推薦標籤時才攔截 Enter 鍵
                if (this.selectedIndex >= 0) {
                    e.preventDefault();
                    this.select(this.selectedIndex);
                } else {
                    // 如果沒有選中任何推薦標籤，隱藏下拉選單並讓 Enter 鍵正常執行其默認行為
                    this.hide();
                }
                break;
            case 'Escape':
                this.hide();
                break;
        }
    }
    
    select(index) {
        const tag = this.tags[index];
        if (tag && this.onSelect) {
            this.onSelect(tag);
            this.input.value = '';
            this.hide();
        }
    }
    
    show() {
        if (this.tags.length > 0) {
            this.dropdown.style.display = 'block';
        } else {
            this.hide();
        }
    }
    
    hide() {
        this.dropdown.style.display = 'none';
        this.selectedIndex = -1;
    }
    
    // 新增: 獲取選中的分類
    getSelectedCategory() {
        if (this.categorySelector) {
            const selector = document.getElementById(this.categorySelector);
            if (selector) {
                const selectedOption = selector.options[selector.selectedIndex];
                if (selectedOption) {
                    // 從選項文字中提取分類名稱，例如 "綠色 (位置)" -> "位置"
                    const match = selectedOption.textContent.match(/\(([^)]+)\)/);
                    return match ? match[1] : null;
                }
            }
        }
        return null;
    }
    
    // 新增: 處理手動輸入的文字，自動添加分類前綴
    createTagWithAutoPrefix(inputText) {
        if (!this.autoPrefix) {
            return {
                name: inputText,
                category: '其他',
                color: '#6c757d'
            };
        }
        
        const selectedCategory = this.getSelectedCategory();
        if (selectedCategory) {
            return {
                name: inputText,
                category: selectedCategory,
                color: this.getCategoryColor(selectedCategory)
            };
        }
        
        // 如果沒有選中分類，檢查是否已經包含分類前綴
        if (inputText.includes(':')) {
            const parts = inputText.split(':', 2);
            return {
                name: parts[1].trim(),
                category: parts[0].trim(),
                color: this.getCategoryColor(parts[0].trim())
            };
        }
        
        return {
            name: inputText,
            category: '其他',
            color: '#6c757d'
        };
    }
    
    // 新增: 根據分類獲取顏色
    getCategoryColor(category) {
        const categoryColors = {
            '手法': '#007bff',
            '症狀': '#dc3545', 
            '位置': '#28a745',
            '施術位置': '#17a2b8',
            '治療位置': '#ffc107',
            '領域': '#6610f2',
            '病因': '#fd7e14',
            '其他': '#6c757d'
        };
        return categoryColors[category] || '#6c757d';
    }
}

// 增強的檔案上傳處理
class FileUploader {
    constructor(options = {}) {
        this.maxSize = options.maxSize || 100 * 1024 * 1024; // 100MB
        this.acceptedTypes = options.acceptedTypes || ['image/*', 'video/*', '.pdf', '.doc', '.docx'];
        this.onProgress = options.onProgress || (() => {});
        this.onComplete = options.onComplete || (() => {});
        this.onError = options.onError || ((error) => { 
            console.error("File upload error:", error); 
            showNotification('上傳失敗: ' + error, 'error'); 
        });
    }
    
    async upload(file, segmentId, options = {}) {
        if (file.size > this.maxSize) {
            const errorMsg = `檔案大小超過限制 (最大 ${this.maxSize / 1024 / 1024}MB)`;
            this.onError(errorMsg);
            return null;
        }

        // 檔案類型檢查
        let typeMatch = false;
        const fileName = file.name.toLowerCase();
        const fileType = file.type;

        for (const acceptedType of this.acceptedTypes) {
            if (acceptedType.startsWith('.')) {
                if (fileName.endsWith(acceptedType)) {
                    typeMatch = true;
                    break;
                }
            } else if (acceptedType.endsWith('/*')) {
                if (fileType.startsWith(acceptedType.slice(0, -2))) {
                    typeMatch = true;
                    break;
                }
            } else {
                if (fileType === acceptedType) {
                    typeMatch = true;
                    break;
                }
            }
        }

        if (!typeMatch) {
            const errorMsg = `不支援的檔案類型: "${file.name}". 可接受的類型: ${this.acceptedTypes.join(', ')}`;
            this.onError(errorMsg);
            return null;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        if (segmentId) {
            formData.append('segment_id', segmentId);
        }
        if (options.description) {
            formData.append('description', options.description);
        }
        
        try {
            const xhr = new XMLHttpRequest();
            
            return new Promise((resolve, reject) => {
                xhr.upload.addEventListener('progress', (e) => {
                    if (e.lengthComputable) {
                        const percentComplete = (e.loaded / e.total) * 100;
                        this.onProgress(percentComplete);
                    }
                });
                
                xhr.addEventListener('load', () => {
                    if (xhr.status === 200) {
                        try {
                            const response = JSON.parse(xhr.responseText);
                            this.onComplete(response);
                            resolve(response);
                        } catch (e) {
                            const errorMsg = '上傳成功，但解析回應失敗。';
                            this.onError(errorMsg);
                            reject(new Error(errorMsg));
                        }
                    } else {
                        let errorMsg = '上傳失敗';
                        try {
                             const errResp = JSON.parse(xhr.responseText);
                             if (errResp && errResp.error) {
                                errorMsg = `上傳失敗: ${errResp.error}`;
                             }
                        } catch(e) {
                            errorMsg = `上傳失敗 (狀態碼: ${xhr.status})`;
                        }
                        this.onError(errorMsg);
                        reject(new Error(errorMsg));
                    }
                });
                
                xhr.addEventListener('error', () => {
                    const errorMsg = '網路錯誤，無法完成上傳。';
                    this.onError(errorMsg);
                    reject(new Error(errorMsg));
                });
                
                xhr.open('POST', `${API_BASE}/upload`);
                xhr.send(formData);
            });
            
        } catch (error) {
            const catchErrorMsg = error.message || '上傳過程中發生未知錯誤。';
            this.onError(catchErrorMsg);
            return Promise.reject(new Error(catchErrorMsg));
        }
    }
}

// 新增：通知系統
class NotificationSystem {
    constructor() {
        this.container = null;
        this.init();
    }
    
    init() {
        // 創建通知容器
        this.container = document.createElement('div');
        this.container.id = 'notification-container';
        this.container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 400px;
        `;
        document.body.appendChild(this.container);
    }
    
    show(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show`;
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        this.container.appendChild(notification);
        
        // 自動隱藏
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, duration);
        
        return notification;
    }
}

// 全域通知系統實例
const notificationSystem = new NotificationSystem();

// 簡化的通知函數
function showNotification(message, type = 'info', duration = 5000) {
    return notificationSystem.show(message, type, duration);
}

// 新增：鍵盤快捷鍵管理
class KeyboardShortcuts {
    constructor() {
        this.shortcuts = new Map();
        this.init();
    }
    
    init() {
        document.addEventListener('keydown', (e) => this.handleKeydown(e));
        
        // 註冊預設快捷鍵
        this.register('ctrl+s', (e) => {
            e.preventDefault();
            this.handleSave();
        });
        
        this.register('ctrl+shift+n', (e) => {
            e.preventDefault();
            window.location.href = '/session/new';
        });
        
        this.register('ctrl+shift+s', (e) => {
            e.preventDefault();
            window.location.href = '/search';
        });
        
        this.register('ctrl+shift+t', (e) => {
            e.preventDefault();
            window.location.href = '/statistics';
        });
        
        this.register('ctrl+shift+b', (e) => {
            e.preventDefault();
            window.location.href = '/batch-operations';
        });
    }
    
    register(shortcut, handler) {
        this.shortcuts.set(shortcut.toLowerCase(), handler);
    }
    
    handleKeydown(e) {
        const key = this.getKeyString(e);
        const handler = this.shortcuts.get(key);
        
        if (handler) {
            handler(e);
        }
    }
    
    getKeyString(e) {
        const parts = [];
        
        if (e.ctrlKey) parts.push('ctrl');
        if (e.shiftKey) parts.push('shift');
        if (e.altKey) parts.push('alt');
        if (e.metaKey) parts.push('meta');
        
        parts.push(e.key.toLowerCase());
        
        return parts.join('+');
    }
    
    handleSave() {
        const activeForm = document.activeElement?.closest('form');
        if (activeForm) {
            const submitButton = activeForm.querySelector('button[type="submit"], input[type="submit"]');
            if (submitButton) {
                submitButton.click();
                showNotification('表單已提交', 'success');
            }
        }
    }
}

// 新增：本地儲存管理
class LocalStorageManager {
    constructor() {
        this.prefix = 'knowledge_system_';
    }
    
    set(key, value) {
        try {
            localStorage.setItem(this.prefix + key, JSON.stringify(value));
            return true;
        } catch (error) {
            console.error('儲存到本地儲存失敗:', error);
            return false;
        }
    }
    
    get(key) {
        try {
            const item = localStorage.getItem(this.prefix + key);
            return item ? JSON.parse(item) : null;
        } catch (error) {
            console.error('從本地儲存讀取失敗:', error);
            return null;
        }
    }
    
    remove(key) {
        try {
            localStorage.removeItem(this.prefix + key);
            return true;
        } catch (error) {
            console.error('從本地儲存刪除失敗:', error);
            return false;
        }
    }
    
    clear() {
        try {
            Object.keys(localStorage)
                .filter(key => key.startsWith(this.prefix))
                .forEach(key => localStorage.removeItem(key));
            return true;
        } catch (error) {
            console.error('清空本地儲存失敗:', error);
            return false;
        }
    }
}

// 全域本地儲存管理器
const storage = new LocalStorageManager();

// 新增：搜尋歷史管理
class SearchHistory {
    constructor() {
        this.maxHistory = 20;
        this.storageKey = 'search_history';
    }
    
    add(query) {
        if (!query || query.trim().length < 2) return;
        
        let history = this.getHistory();
        
        // 移除重複項
        history = history.filter(item => item.query !== query.trim());
        
        // 添加到開頭
        history.unshift({
            query: query.trim(),
            timestamp: new Date().toISOString()
        });
        
        // 限制數量
        history = history.slice(0, this.maxHistory);
        
        storage.set(this.storageKey, history);
    }
    
    getHistory() {
        return storage.get(this.storageKey) || [];
    }
    
    clear() {
        storage.remove(this.storageKey);
    }
    
    remove(query) {
        let history = this.getHistory();
        history = history.filter(item => item.query !== query);
        storage.set(this.storageKey, history);
    }
}

// 全域搜尋歷史管理器
const searchHistory = new SearchHistory();

// 新增：性能監控
class PerformanceMonitor {
    constructor() {
        this.metrics = {
            pageLoadTime: 0,
            apiCalls: [],
            userActions: []
        };
        
        this.init();
    }
    
    init() {
        // 監控頁面載入時間
        window.addEventListener('load', () => {
            this.metrics.pageLoadTime = performance.now();
            console.log(`頁面載入時間: ${this.metrics.pageLoadTime.toFixed(2)}ms`);
        });
        
        // 監控 fetch 請求
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            const startTime = performance.now();
            try {
                const response = await originalFetch(...args);
                const endTime = performance.now();
                
                this.metrics.apiCalls.push({
                    url: args[0],
                    duration: endTime - startTime,
                    status: response.status,
                    timestamp: new Date().toISOString()
                });
                
                return response;
            } catch (error) {
                const endTime = performance.now();
                this.metrics.apiCalls.push({
                    url: args[0],
                    duration: endTime - startTime,
                    error: error.message,
                    timestamp: new Date().toISOString()
                });
                throw error;
            }
        };
    }
    
    recordUserAction(action, details = {}) {
        this.metrics.userActions.push({
            action,
            details,
            timestamp: new Date().toISOString()
        });
    }
    
    getMetrics() {
        return this.metrics;
    }
    
    exportMetrics() {
        const data = JSON.stringify(this.metrics, null, 2);
        const blob = new Blob([data], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `performance_metrics_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }
}

// 全域性能監控器
const performanceMonitor = new PerformanceMonitor();

// 全域初始化
document.addEventListener('DOMContentLoaded', function() {
    // 初始化 Bootstrap tooltips
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = Array.from(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.forEach(function (tooltipTriggerEl) {
            new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // 初始化鍵盤快捷鍵
    new KeyboardShortcuts();
    
    // 自動儲存草稿功能
    const sessionForm = document.getElementById('sessionForm');
    if (sessionForm) {
        setupAutoSave(sessionForm, 'sessionForm');
    }
    
    // 初始化搜尋功能
    initializeSearchFeatures();
    
    // 顯示歡迎提示
    showWelcomeMessage();
});

// 設置自動儲存
function setupAutoSave(form, formId) {
    const draftData = loadDraft(formId);
    if (draftData) {
        populateFormWithDraft(form, draftData);
    }

    const inputs = form.querySelectorAll('input, textarea, select');
    inputs.forEach(input => {
        const eventType = (input.type === 'checkbox' || input.type === 'radio' || input.tagName === 'SELECT') ? 'change' : 'input';
        input.addEventListener(eventType, debounce(() => {
            saveDraft(form, formId);
        }, 1000));
    });
}

function populateFormWithDraft(form, draftData) {
    for (const key in draftData) {
        if (Object.prototype.hasOwnProperty.call(draftData, key)) {
            const element = form.elements[key];
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = draftData[key];
                } else if (element.type === 'radio' && element.value === draftData[key]) {
                    element.checked = true;
                } else {
                    element.value = draftData[key];
                }
            }
        }
    }
}

// 草稿管理函數
function saveDraft(form, formId) {
    if (!form || !formId) return;
    
    try {
        const data = {};
        form.querySelectorAll('input, textarea, select').forEach(el => {
            if (el.name) {
                if (el.type === 'checkbox') {
                    data[el.name] = el.checked;
                } else if (el.type === 'radio') {
                    if (el.checked) {
                        data[el.name] = el.value;
                    }
                } else {
                    data[el.name] = el.value;
                }
            }
        });
        
        storage.set(`draft_${formId}`, data);
        console.log(`草稿已儲存: ${formId}`);
    } catch (error) {
        console.error('儲存草稿失敗:', error);
    }
}

function loadDraft(formId) {
    if (!formId) return null;
    return storage.get(`draft_${formId}`);
}

function clearDraft(formId) {
    if (!formId) return;
    storage.remove(`draft_${formId}`);
    console.log(`草稿已清除: ${formId}`);
}

// 初始化搜尋功能
function initializeSearchFeatures() {
    // 設置搜尋歷史
    const searchInputs = document.querySelectorAll('input[type="search"], .search-input');
    searchInputs.forEach(input => {
        input.addEventListener('focus', () => showSearchHistory(input));
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const query = input.value.trim();
                if (query) {
                    searchHistory.add(query);
                }
            }
        });
    });
}

function showSearchHistory(input) {
    const history = searchHistory.getHistory();
    if (history.length === 0) return;
    
    // 創建歷史下拉選單
    let dropdown = input.parentElement.querySelector('.search-history-dropdown');
    if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.className = 'search-history-dropdown autocomplete-dropdown';
        input.parentElement.appendChild(dropdown);
    }
    
    dropdown.innerHTML = history.slice(0, 5).map(item => `
        <div class="autocomplete-item" onclick="selectSearchHistory('${item.query}', this)">
            <i class="fas fa-history text-muted me-2"></i>
            ${item.query}
            <small class="text-muted ms-auto">${new Date(item.timestamp).toLocaleDateString()}</small>
        </div>
    `).join('');
    
    dropdown.style.display = 'block';
    
    // 點擊外部隱藏
    setTimeout(() => {
        document.addEventListener('click', function hideHistory(e) {
            if (!input.contains(e.target) && !dropdown.contains(e.target)) {
                dropdown.style.display = 'none';
                document.removeEventListener('click', hideHistory);
            }
        });
    }, 100);
}

function selectSearchHistory(query, element) {
    const input = element.closest('.search-history-dropdown').previousElementSibling;
    input.value = query;
    element.parentElement.style.display = 'none';
    
    // 觸發搜尋
    const searchEvent = new Event('input', { bubbles: true });
    input.dispatchEvent(searchEvent);
}

// 顯示歡迎訊息
function showWelcomeMessage() {
    const hasSeenWelcome = storage.get('has_seen_welcome');
    if (!hasSeenWelcome) {
        setTimeout(() => {
            showNotification(
                '歡迎使用知識管理系統！使用 Ctrl+Shift+? 查看快捷鍵', 
                'info', 
                8000
            );
            storage.set('has_seen_welcome', true);
        }, 1000);
    }
}

// 匯出功能
async function exportSession(sessionId, format = 'json') {
    if (!sessionId) {
        console.error('匯出失敗: 未提供 sessionId');
        showNotification('匯出失敗: 未提供 session ID。', 'error');
        return;
    }
    
    try {
        showNotification('正在準備匯出...', 'info');
        
        const response = await fetch(`${API_BASE}/api/session/${sessionId}/export?format=${format}`);
        if (!response.ok) {
            let errorDetail = response.statusText;
            try {
                const errorJson = await response.json();
                if (errorJson && errorJson.error) {
                    errorDetail = errorJson.error;
                }
            } catch (e) {
                // 解析失敗，使用原始 statusText
            }
            throw new Error(`匯出失敗: ${errorDetail} (狀態碼: ${response.status})`);
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        const safeSessionId = String(sessionId).replace(/[^a-z0-9_.-]/gi, '_');
        const safeFormat = String(format).replace(/[^a-z0-9_.-]/gi, '_');
        a.download = `session_${safeSessionId}.${safeFormat}`;
        
        document.body.appendChild(a);
        a.click();
        
        // 清理
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showNotification('匯出完成！', 'success');
        
    } catch (error) {
        console.error('匯出操作失敗:', error);
        showNotification(error.message || '匯出失敗，請重試。', 'error');
    }
}

// 列印優化
window.addEventListener('beforeprint', function() {
    console.log("準備列印...");
    // 展開所有可折疊元素
    document.querySelectorAll('.collapse').forEach(el => {
        if (!el.classList.contains('show')) {
            el.classList.add('show');
            el.dataset.printExpanded = 'true';
        }
    });
});

window.addEventListener('afterprint', function() {
    console.log("列印完成");
    // 恢復列印前展開的元素
    document.querySelectorAll('.collapse[data-print-expanded="true"]').forEach(el => {
        el.classList.remove('show');
        el.removeAttribute('data-print-expanded');
    });
});

// 導出全域函數和類別供其他腳本使用
window.KnowledgeSystem = {
    TagAutocomplete,
    FileUploader,
    NotificationSystem,
    KeyboardShortcuts,
    LocalStorageManager,
    SearchHistory,
    PerformanceMonitor,
    // 工具函數
    showNotification,
    exportSession,
    saveDraft,
    loadDraft,
    clearDraft,
    debounce
};
