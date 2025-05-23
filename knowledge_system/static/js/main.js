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

// 標籤自動完成系統
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
        // Ensure input parent is positioned relatively for dropdown absolute positioning
        if (this.input.parentElement) {
            this.input.parentElement.style.position = 'relative'; 
            this.input.parentElement.appendChild(this.dropdown);
        } else {
            console.error("TagAutocomplete input element must have a parent.");
            return;
        }
        
        // 綁定事件
        this.input.addEventListener('input', debounce(() => this.search(), 300));
        this.input.addEventListener('keydown', (e) => this.handleKeydown(e));
        document.addEventListener('click', (e) => {
            if (this.dropdown && !this.input.contains(e.target) && !this.dropdown.contains(e.target)) {
                this.hide();
            }
        });
    }
    
    async search() {
        const query = this.input.value.trim();
        if (query.length < 1) { // Changed from < 2 to < 1 for more responsive search
            this.hide();
            return;
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/tags/search?q=${encodeURIComponent(query)}`);
            this.tags = await response.json();
            this.render();
        } catch (error) {
            console.error('搜尋標籤失敗:', error);
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
                <span class="badge" style="background-color: ${tag.color || '#6c757d'}">${tag.category}</span>
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
            this.input.value = ''; // Clear input after selection
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
        // Do not clear this.tags here, it might be needed if input changes slightly
    }
}

// 檔案上傳處理
class FileUploader {
    constructor(options = {}) { // Added default for options
        this.maxSize = options.maxSize || 100 * 1024 * 1024; // 100MB
        this.acceptedTypes = options.acceptedTypes || ['image/*', 'video/*', '.pdf', '.doc', '.docx'];
        this.onProgress = options.onProgress || (() => {});
        this.onComplete = options.onComplete || (() => {});
        this.onError = options.onError || ((error) => { console.error("File upload error:", error); alert(error); });
    }
    
    async upload(file, segmentId) { // Added segmentId to associate file
        if (file.size > this.maxSize) {
            this.onError(`檔案大小超過限制 (最大 ${this.maxSize / 1024 / 1024}MB)`);
            return null; // Return null on error
        }
        
        const formData = new FormData();
        formData.append('file', file);
        if (segmentId) { // Optional: send segmentId if available
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
                            resolve(response); // Resolve promise with response
                        } catch (e) {
                            this.onError('上傳成功，但解析回應失敗。');
                            reject('上傳成功，但解析回應失敗。');
                        }
                    } else {
                        let errorMsg = '上傳失敗';
                        try {
                             const errResp = JSON.parse(xhr.responseText);
                             errorMsg = errResp.error || errorMsg;
                        } catch(e) {/* ignore */}
                        this.onError(`${errorMsg} (狀態碼: ${xhr.status})`);
                        reject(`${errorMsg} (狀態碼: ${xhr.status})`);
                    }
                });
                
                xhr.addEventListener('error', () => {
                    this.onError('網路錯誤');
                    reject('網路錯誤');
                });
                
                xhr.open('POST', `${API_BASE}/upload`); // Ensure API_BASE is defined
                xhr.send(formData);
            });
            
        } catch (error) {
            this.onError(error.message);
            return null; // Return null on error
        }
    }
}

// 關聯圖視覺化 (Placeholder)
class RelationGraph {
    constructor(container) {
        this.container = container;
        this.nodes = [];
        this.links = [];
        this.svg = null;
        this.simulation = null;
        
        if (!window.d3) {
            console.warn("D3.js is not loaded. RelationGraph will not function.");
            this.container.innerHTML = "<p class='text-center text-danger'>D3.js 圖形庫未載入，無法顯示關聯圖。</p>";
            return;
        }
         this.container.innerHTML = ""; // Clear placeholder text
    }
    
    init(data) {
        if (!window.d3) return;
        // Basic D3.js setup example
        console.log('初始化關聯圖', data);
        this.nodes = data.nodes || [];
        this.links = data.links || [];

        const width = this.container.clientWidth;
        const height = this.container.clientHeight || 600;

        this.svg = d3.select(this.container).append("svg")
            .attr("width", width)
            .attr("height", height)
            .call(d3.zoom().on("zoom", (event) => {
               g.attr("transform", event.transform);
            }))
            .append("g");
        
        const g = this.svg; // Group for zooming

        this.simulation = d3.forceSimulation(this.nodes)
            .force("link", d3.forceLink(this.links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-150))
            .force("center", d3.forceCenter(width / 2, height / 2));

        const link = g.append("g")
            .attr("stroke", "#999")
            .attr("stroke-opacity", 0.6)
            .selectAll("line")
            .data(this.links)
            .join("line")
            .attr("stroke-width", d => Math.sqrt(d.value || 1));

        const node = g.append("g")
            .attr("stroke", "#fff")
            .attr("stroke-width", 1.5)
            .selectAll("circle")
            .data(this.nodes)
            .join("circle")
            .attr("r", 10)
            .attr("fill", d => d.color || "#3498db")
            .call(this.drag(this.simulation));

        node.append("title")
            .text(d => d.name);

        this.simulation.on("tick", () => {
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
        });
    }

    drag(simulation) {
      function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      }
      function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
      }
      function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      }
      return d3.drag()
          .on("start", dragstarted)
          .on("drag", dragged)
          .on("end", dragended);
    }

    update() {
        // More sophisticated update logic if needed
        console.log('更新關聯圖');
        // This might involve re-running the simulation or updating data binds
        if (this.simulation && this.svg) {
             // Update nodes
            const node = this.svg.select("g").selectAll("circle").data(this.nodes, d => d.id);
            node.enter().append("circle")
                // ... (attributes for new nodes)
                .call(this.drag(this.simulation));
            node.exit().remove();
            
            // Update links
            const link = this.svg.select("g").selectAll("line").data(this.links, d => `${d.source.id}-${d.target.id}`);
            link.enter().append("line")
                // ... (attributes for new links)
            link.exit().remove();

            this.simulation.nodes(this.nodes);
            this.simulation.force("link").links(this.links);
            this.simulation.alpha(1).restart();
        }
    }
}


// 全域初始化
document.addEventListener('DOMContentLoaded', function() {
    // 初始化 Bootstrap tooltips
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // 自動儲存草稿 (Example for a form with id "sessionForm")
    const sessionForm = document.getElementById('sessionForm');
    if (sessionForm) {
        // Load draft
        const draftData = loadDraft('sessionForm');
        if (draftData) {
            for (const key in draftData) {
                if (sessionForm.elements[key]) {
                    sessionForm.elements[key].value = draftData[key];
                }
            }
            // Handle customTags if they were part of the draft
            if (draftData.customTags_json) { // Assuming you stringify arrays for localStorage
                customTags = JSON.parse(draftData.customTags_json);
                if (typeof updateCustomTags === 'function') updateCustomTags();
            }
        }

        // Save draft on input
        const inputs = sessionForm.querySelectorAll('input, textarea');
        inputs.forEach(input => {
            input.addEventListener('input', debounce(() => {
                saveDraft(sessionForm, 'sessionForm');
            }, 1000));
        });
        
        // Clear draft on successful submit
        sessionForm.addEventListener('submit', function() {
            // Assuming submit leads to navigation or success message
            // Clear draft after a short delay to allow submission to process
            setTimeout(() => clearDraft('sessionForm'), 2000); 
        });
    }
});

// 儲存草稿
function saveDraft(form, formId) {
    if (!form || !formId) return;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    // If there's a global customTags array related to this form, save it too.
    if (formId === 'sessionForm' && typeof customTags !== 'undefined') {
        data.customTags_json = JSON.stringify(customTags); // Store as JSON string
    }
    localStorage.setItem(`draft_${formId}`, JSON.stringify(data));
    console.log(`Draft saved for ${formId}`);
}

// 載入草稿
function loadDraft(formId) {
    const draft = localStorage.getItem(`draft_${formId}`);
    if (draft) {
        console.log(`Draft loaded for ${formId}`);
        return JSON.parse(draft);
    }
    return null;
}

// 清除草稿
function clearDraft(formId) {
    localStorage.removeItem(`draft_${formId}`);
    console.log(`Draft cleared for ${formId}`);
}

// 匯出功能 (Placeholder - needs server-side implementation)
async function exportSession(sessionId, format = 'json') {
    try {
        // This endpoint `/api/session/${sessionId}/export` needs to be implemented on the server
        const response = await fetch(`${API_BASE}/api/session/${sessionId}/export?format=${format}`);
        if (!response.ok) {
            throw new Error(`匯出失敗: ${response.statusText}`);
        }
        const blob = await response.blob();
        
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `session_${sessionId}.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        console.error('匯出失敗:', error);
        alert('匯出失敗，請重試。請確保伺服器端已實現匯出功能。');
    }
}

// 快捷鍵支援
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + S: 儲存 (Trigger submit on active form)
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        const activeForm = document.querySelector('form:focus-within');
        if (activeForm && typeof activeForm.requestSubmit === 'function') {
            activeForm.requestSubmit();
        } else if (activeForm) {
            // Fallback for older browsers or forms without a submit button in focus
            const submitButton = activeForm.querySelector('button[type="submit"], input[type="submit"]');
            if (submitButton) submitButton.click();
        }
    }
    
    // Ctrl/Cmd + Enter: 快速提交 (If a textarea or specific input is focused)
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        const activeElement = document.activeElement;
        if (activeElement && (activeElement.tagName === 'TEXTAREA' || activeElement.matches('input[type="text"]'))) {
            const form = activeElement.closest('form');
            if (form && typeof form.requestSubmit === 'function') {
                e.preventDefault();
                form.requestSubmit();
            } else if (form) {
                 const submitButton = form.querySelector('button[type="submit"], input[type="submit"]');
                 if (submitButton) {
                    e.preventDefault();
                    submitButton.click();
                 }
            }
        }
    }
});

// 列印優化
window.addEventListener('beforeprint', function() {
    console.log("Preparing for print...");
    // Example: Expand all collapsible elements
    document.querySelectorAll('.collapse').forEach(el => {
        if (bootstrap && bootstrap.Collapse) { // Check if bootstrap Collapse is available
            const collapseInstance = bootstrap.Collapse.getInstance(el) || new bootstrap.Collapse(el, {toggle: false});
            collapseInstance.show();
        } else {
            el.classList.add('show'); // Fallback if Bootstrap JS not fully initialized
        }
    });
});

window.addEventListener('afterprint', function() {
    console.log("Finished printing.");
    // Example: Restore collapsible elements to their original state if needed
    // This might be complex if you need to track original states.
    // For simplicity, just removing 'show' might be okay for some cases.
    document.querySelectorAll('.collapse.show').forEach(el => {
         if (bootstrap && bootstrap.Collapse) {
            const collapseInstance = bootstrap.Collapse.getInstance(el);
            // Only hide if it was programmatically shown and not originally shown
            // This requires more state management, for now, we can just re-hide.
            // Or better, let user manage state.
         }
    });
});

// Make sure D3 is loaded for RelationGraph, can be added to base.html if needed for search page
// <script src="https://d3js.org/d3.v7.min.js"></script>
