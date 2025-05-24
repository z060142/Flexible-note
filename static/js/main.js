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

// 標籤自動完成系統 - 修復版本
class TagAutocomplete {
    constructor(inputElement, onSelect) {
        this.input = inputElement;
        this.onSelect = onSelect;
        this.dropdown = null;
        this.tags = [];
        this.selectedIndex = -1;
        
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
            const response = await fetch(`${API_BASE}/api/tags/search?q=${encodeURIComponent(query)}`);
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
                e.preventDefault();
                if (this.selectedIndex >= 0) {
                    this.select(this.selectedIndex);
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
}

// 修復後的檔案上傳處理
class FileUploader {
    constructor(options = {}) {
        this.maxSize = options.maxSize || 100 * 1024 * 1024; // 100MB
        this.acceptedTypes = options.acceptedTypes || ['image/*', 'video/*', '.pdf', '.doc', '.docx'];
        this.onProgress = options.onProgress || (() => {});
        this.onComplete = options.onComplete || (() => {});
        this.onError = options.onError || ((error) => { 
            console.error("File upload error:", error); 
            alert('上傳失敗: ' + error); 
        });
    }
    
    async upload(file, segmentId) {
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
            if (acceptedType.startsWith('.')) { // 副檔名檢查
                if (fileName.endsWith(acceptedType)) {
                    typeMatch = true;
                    break;
                }
            } else if (acceptedType.endsWith('/*')) { // MIME 主類型檢查 (e.g., 'image/*')
                if (fileType.startsWith(acceptedType.slice(0, -2))) {
                    typeMatch = true;
                    break;
                }
            } else { // 精確 MIME 類型檢查
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
                            reject(new Error(errorMsg)); // Reject with an Error object
                        }
                    } else {
                        let errorMsg = '上傳失敗';
                        try {
                             const errResp = JSON.parse(xhr.responseText);
                             if (errResp && errResp.error) {
                                errorMsg = `上傳失敗: ${errResp.error}`;
                             } else if (xhr.responseText) {
                                // 避免顯示過長的 HTML 錯誤頁面作為訊息
                                errorMsg = `上傳失敗: ${xhr.responseText.length > 150 ? xhr.responseText.substring(0, 150) + '...' : xhr.responseText}`;
                             }
                        } catch(e) {
                            // 忽略解析錯誤，使用預設訊息
                            if (xhr.responseText && xhr.responseText.length > 0 && xhr.responseText.length < 150) {
                                 errorMsg = `上傳失敗: ${xhr.responseText}`;
                            } else if (xhr.responseText) {
                                errorMsg = `上傳失敗，伺服器回應無法解析。`;
                            }
                        }
                        errorMsg += ` (狀態碼: ${xhr.status})`;
                        this.onError(errorMsg);
                        reject(new Error(errorMsg)); // Reject with an Error object
                    }
                });
                
                xhr.addEventListener('error', () => {
                    const errorMsg = '網路錯誤，無法完成上傳。';
                    this.onError(errorMsg);
                    reject(new Error(errorMsg)); // Reject with an Error object
                });
                
                xhr.open('POST', `${API_BASE}/upload`);
                xhr.send(formData);
            });
            
        } catch (error) {
            // 這個 catch 主要捕捉 xhr 物件創建或同步操作的錯誤
            const catchErrorMsg = error.message || '上傳過程中發生未知客戶端錯誤。';
            this.onError(catchErrorMsg);
            // 確保 upload 方法在出錯時回傳 Promise.reject
            return Promise.reject(new Error(catchErrorMsg));
        }
    }
}

// 關聯圖視覺化 (基礎版本)
class RelationGraph {
    constructor(container) {
        this.container = container;
        this.nodes = [];
        this.links = [];
        this.svg = null;
        
        if (!container) {
            console.error("RelationGraph container is required");
            // 可以考慮拋出錯誤或設定一個標誌表示實例無效
            // throw new Error("RelationGraph: container 元素是必需的，但未提供。");
            return;
        }
        
        this.container.innerHTML = "<p class='text-center text-muted'>關聯圖功能需要 D3.js 圖形庫支援</p>";
    }
    
    init(data) {
        console.log('初始化關聯圖', data);
        this.nodes = data.nodes || [];
        this.links = data.links || [];
        
        // 簡單的文字顯示，直到 D3.js 可用
        if (this.nodes.length > 0) {
            let html = '<div class="relation-display"><h6>節點關聯：</h6><ul>';
            this.nodes.forEach(node => {
                html += `<li>${node.name} (${node.type || 'unknown'})</li>`;
            });
            html += '</ul></div>';
            this.container.innerHTML = html;
        } else if (this.links.length > 0) { // 如果只有連結資料也提示
             this.container.innerHTML = "<p class='text-center text-muted'>收到關聯資料，但無節點可顯示或 D3.js 未載入。</p>";
        } else {
            this.container.innerHTML = "<p class='text-center text-muted'>無關聯資料可顯示或 D3.js 未載入。</p>";
        }
    }
}

// 全域初始化
document.addEventListener('DOMContentLoaded', function() {
    // 初始化 Bootstrap tooltips
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = Array.from(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.forEach(function (tooltipTriggerEl) {
            new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // 自動儲存草稿功能
    const sessionForm = document.getElementById('sessionForm');
    if (sessionForm) {
        const draftData = loadDraft('sessionForm');
        if (draftData) {
            for (const key in draftData) {
                if (Object.prototype.hasOwnProperty.call(draftData, key)) { // 確保是自身屬性
                    const element = sessionForm.elements[key];
                    if (element) {
                        // 對於 checkbox 和 radio button 需要特殊處理
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

        const inputs = sessionForm.querySelectorAll('input, textarea, select'); // 包含 select
        inputs.forEach(input => {
            const eventType = (input.type === 'checkbox' || input.type === 'radio' || input.tagName === 'SELECT') ? 'change' : 'input';
            input.addEventListener(eventType, debounce(() => {
                saveDraft(sessionForm, 'sessionForm');
            }, 1000));
        });
    }
});

// 草稿管理函數
function saveDraft(form, formId) {
    if (!form || !formId) return;
    
    try {
        const formData = new FormData(form);
        const data = {};
        // FormData.entries() 可能不包含未選中的 checkbox，需要手動處理
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
        localStorage.setItem(`draft_${formId}`, JSON.stringify(data));
        console.log(`Draft saved for ${formId}`);
    } catch (error) {
        console.error('保存草稿失敗:', error);
        // 可以考慮更友善的錯誤提示，例如通知使用者草稿保存失敗
    }
}

function loadDraft(formId) {
    if (!formId) return null;
    try {
        const draft = localStorage.getItem(`draft_${formId}`);
        if (draft) {
            console.log(`Draft loaded for ${formId}`);
            return JSON.parse(draft);
        }
    } catch (error) {
        console.error('載入草稿失敗:', error);
        // 如果解析失敗，可能草稿已損壞，可以考慮清除它
        // localStorage.removeItem(`draft_${formId}`);
    }
    return null;
}

function clearDraft(formId) {
    if (!formId) return;
    try {
        localStorage.removeItem(`draft_${formId}`);
        console.log(`Draft cleared for ${formId}`);
    } catch (error) {
        console.error('清除草稿失敗:', error);
    }
}

// 匯出功能
async function exportSession(sessionId, format = 'json') {
    if (!sessionId) {
        console.error('匯出失敗: 未提供 sessionId');
        alert('匯出失敗: 未提供 session ID。');
        return;
    }
    try {
        const response = await fetch(`${API_BASE}/api/session/${sessionId}/export?format=${format}`);
        if (!response.ok) {
            // 嘗試解析錯誤回應
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
        // 確保檔名安全
        const safeSessionId = String(sessionId).replace(/[^a-z0-9_.-]/gi, '_');
        const safeFormat = String(format).replace(/[^a-z0-9_.-]/gi, '_');
        a.download = `session_${safeSessionId}.${safeFormat}`;
        
        document.body.appendChild(a);
        a.click();
        
        // 清理
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
    } catch (error) {
        console.error('匯出操作失敗:', error);
        alert(error.message || '匯出失敗，請重試。');
    }
}

// 快捷鍵支援
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + S: 儲存
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        // 檢查是否在輸入欄位中，避免與瀏覽器本身的儲存快捷鍵衝突
        const activeElement = document.activeElement;
        if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA' || activeElement.isContentEditable)) {
            e.preventDefault();
            const activeForm = activeElement.closest('form');
            if (activeForm) {
                // 優先觸發 'submit' 事件而非 click，以便執行表單驗證
                if (typeof activeForm.requestSubmit === 'function') {
                    activeForm.requestSubmit();
                } else {
                    const submitButton = activeForm.querySelector('button[type="submit"], input[type="submit"]');
                    if (submitButton) {
                        submitButton.click();
                    } else {
                        // 如果沒有明確的 submit button，嘗試觸發 submit 事件
                        const submitEvent = new Event('submit', { bubbles: true, cancelable: true });
                        activeForm.dispatchEvent(submitEvent);
                    }
                }
                 console.log('Ctrl+S: 嘗試提交表單');
            } else {
                console.log('Ctrl+S: 未找到活動表單');
            }
        }
    }
    
    // Ctrl/Cmd + Enter: 快速提交
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        const activeElement = document.activeElement;
        if (activeElement && (activeElement.tagName === 'TEXTAREA' || (activeElement.tagName === 'INPUT' && activeElement.type === 'text'))) {
            const form = activeElement.closest('form');
            if (form) {
                e.preventDefault(); // 阻止 Enter 的預設行為 (例如換行)
                if (typeof form.requestSubmit === 'function') {
                    form.requestSubmit();
                } else {
                    const submitButton = form.querySelector('button[type="submit"], input[type="submit"]');
                    if (submitButton) {
                        submitButton.click();
                    } else {
                        const submitEvent = new Event('submit', { bubbles: true, cancelable: true });
                        form.dispatchEvent(submitEvent);
                    }
                }
                console.log('Ctrl+Enter: 嘗試提交表單');
            }
        }
    }
});

// 列印優化
window.addEventListener('beforeprint', function() {
    console.log("準備列印...");
    // 展開所有可折疊元素
    document.querySelectorAll('.collapse').forEach(el => {
        if (!el.classList.contains('show')) {
            el.classList.add('show');
            el.dataset.printExpanded = 'true'; // 標記為由列印展開
        }
    });
    // 可以在此處添加更多列印特定樣式或操作
});

window.addEventListener('afterprint', function() {
    console.log("列印完成");
    // 恢復列印前展開的元素
    document.querySelectorAll('.collapse[data-print-expanded="true"]').forEach(el => {
        el.classList.remove('show');
        el.removeAttribute('data-print-expanded');
    });
    // 可以在此處移除列印特定樣式或操作
});
