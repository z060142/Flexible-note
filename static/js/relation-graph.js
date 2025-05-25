// 關聯圖譜可視化組件
class RelationGraph {
    constructor(container) {
        this.container = container;
        this.width = container.clientWidth || 800;
        this.height = container.clientHeight || 600;
        this.svg = null;
        this.simulation = null;
        this.data = null;
        this.tooltip = null;
        
        this.init();
    }
    
    init() {
        // 清空容器
        this.container.innerHTML = '';
        
        // 創建SVG
        this.svg = d3.select(this.container)
            .append('svg')
            .attr('width', this.width)
            .attr('height', this.height)
            .style('border', '1px solid #ddd')
            .style('border-radius', '8px');
            
        // 創建容器群組
        this.g = this.svg.append('g');
        
        // 添加縮放行為
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                this.g.attr('transform', event.transform);
            });
            
        this.svg.call(zoom);
        
        // 創建提示框
        this.createTooltip();
        
        // 創建圖例
        this.createLegend();
        
        // 創建控制面板
        this.createControls();
    }
    
    createTooltip() {
        this.tooltip = d3.select('body')
            .append('div')
            .attr('class', 'relation-tooltip')
            .style('position', 'absolute')
            .style('background', 'rgba(0, 0, 0, 0.8)')
            .style('color', 'white')
            .style('padding', '8px')
            .style('border-radius', '4px')
            .style('font-size', '12px')
            .style('pointer-events', 'none')
            .style('opacity', 0)
            .style('z-index', 1000);
    }
    
    createLegend() {
        const legend = this.svg.append('g')
            .attr('class', 'legend')
            .attr('transform', `translate(20, 20)`);
            
        const categories = [
            { name: '症狀', color: '#dc3545' },
            { name: '病因', color: '#fd7e14' },
            { name: '手法', color: '#007bff' },
            { name: '位置', color: '#28a745' },
            { name: '領域', color: '#6610f2' },
            { name: '其他', color: '#6c757d' }
        ];
        
        const legendItems = legend.selectAll('.legend-item')
            .data(categories)
            .enter()
            .append('g')
            .attr('class', 'legend-item')
            .attr('transform', (d, i) => `translate(0, ${i * 20})`);
            
        legendItems.append('circle')
            .attr('r', 6)
            .attr('fill', d => d.color);
            
        legendItems.append('text')
            .attr('x', 15)
            .attr('y', 4)
            .style('font-size', '12px')
            .style('fill', '#333')
            .text(d => d.name);
    }
    
    createControls() {
        const controls = d3.select(this.container)
            .append('div')
            .attr('class', 'graph-controls')
            .style('position', 'absolute')
            .style('top', '10px')
            .style('right', '10px')
            .style('background', 'white')
            .style('padding', '10px')
            .style('border-radius', '4px')
            .style('box-shadow', '0 2px 4px rgba(0,0,0,0.1)');
            
        // 重置視圖按鈕
        controls.append('button')
            .attr('class', 'btn btn-sm btn-outline-primary me-2')
            .style('margin-right', '5px')
            .text('重置視圖')
            .on('click', () => {
                this.svg.transition()
                    .duration(750)
                    .call(d3.zoom().transform, d3.zoomIdentity);
            });
            
        // 居中顯示按鈕
        controls.append('button')
            .attr('class', 'btn btn-sm btn-outline-secondary')
            .text('居中顯示')
            .on('click', () => {
                this.centerGraph();
            });
    }
    
    setData(data) {
        this.data = data;
        this.render();
    }
    
    render() {
        if (!this.data || !this.data.nodes || !this.data.links) {
            this.container.innerHTML = '<p class="text-center text-muted">沒有可視化數據</p>';
            return;
        }
        
        // 清除之前的圖形
        this.g.selectAll('*').remove();
        
        // 創建力導向模擬
        this.simulation = d3.forceSimulation(this.data.nodes)
            .force('link', d3.forceLink(this.data.links)
                .id(d => d.id)
                .distance(d => 50 + (1 - d.strength) * 100))
            .force('charge', d3.forceManyBody()
                .strength(d => -300 - d.importance * 50))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2))
            .force('collision', d3.forceCollide(d => d.size + 5));
            
        // 繪製連線
        this.renderLinks();
        
        // 繪製節點
        this.renderNodes();
        
        // 啟動模擬
        this.simulation.on('tick', () => {
            this.updatePositions();
        });
    }
    
    renderLinks() {
        this.links = this.g.append('g')
            .attr('class', 'links')
            .selectAll('line')
            .data(this.data.links)
            .enter()
            .append('line')
            .attr('stroke', d => this.getLinkColor(d.relation_type))
            .attr('stroke-width', d => Math.max(1, d.strength * 3))
            .attr('stroke-opacity', 0.6)
            .attr('stroke-dasharray', d => d.relation_type === 'same_category' ? '5,5' : null);
            
        // 連線標籤
        this.linkLabels = this.g.append('g')
            .attr('class', 'link-labels')
            .selectAll('text')
            .data(this.data.links.filter(d => d.strength > 0.5))
            .enter()
            .append('text')
            .attr('class', 'link-label')
            .style('font-size', '10px')
            .style('fill', '#666')
            .style('text-anchor', 'middle')
            .text(d => this.getRelationLabel(d.relation_type));
    }
    
    renderNodes() {
        this.nodes = this.g.append('g')
            .attr('class', 'nodes')
            .selectAll('g')
            .data(this.data.nodes)
            .enter()
            .append('g')
            .attr('class', 'node')
            .call(d3.drag()
                .on('start', (event, d) => this.dragStarted(event, d))
                .on('drag', (event, d) => this.dragged(event, d))
                .on('end', (event, d) => this.dragEnded(event, d)));
                
        // 節點圓圈
        this.nodes.append('circle')
            .attr('r', d => d.size)
            .attr('fill', d => d.color)
            .attr('stroke', '#fff')
            .attr('stroke-width', 2)
            .style('cursor', 'pointer');
            
        // 節點標籤
        this.nodes.append('text')
            .attr('dy', d => d.size + 15)
            .attr('text-anchor', 'middle')
            .style('font-size', '11px')
            .style('font-weight', d => d.level === 0 ? 'bold' : 'normal')
            .style('fill', '#333')
            .text(d => d.name.length > 8 ? d.name.substring(0, 8) + '...' : d.name);
            
        // 添加事件監聽
        this.nodes
            .on('mouseover', (event, d) => this.showTooltip(event, d))
            .on('mouseout', () => this.hideTooltip())
            .on('click', (event, d) => this.nodeClicked(event, d));
    }
    
    updatePositions() {
        this.links
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
            
        this.linkLabels
            .attr('x', d => (d.source.x + d.target.x) / 2)
            .attr('y', d => (d.source.y + d.target.y) / 2);
            
        this.nodes
            .attr('transform', d => `translate(${d.x}, ${d.y})`);
    }
    
    dragStarted(event, d) {
        if (!event.active) this.simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }
    
    dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }
    
    dragEnded(event, d) {
        if (!event.active) this.simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }
    
    showTooltip(event, d) {
        const connections = this.data.links.filter(link => 
            link.source.id === d.id || link.target.id === d.id
        ).length;
        
        this.tooltip.transition()
            .duration(200)
            .style('opacity', .9);
            
        this.tooltip.html(`
            <strong>${d.name}</strong><br/>
            分類: ${d.category}<br/>
            層級: ${d.level}<br/>
            連接數: ${connections}<br/>
            重要性: ${d.importance}
        `)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 28) + 'px');
    }
    
    hideTooltip() {
        this.tooltip.transition()
            .duration(500)
            .style('opacity', 0);
    }
    
    nodeClicked(event, d) {
        // 高亮顯示相關節點和連線
        this.highlightConnected(d);
        
        // 觸發自定義事件
        const customEvent = new CustomEvent('nodeClick', {
            detail: { node: d, graph: this }
        });
        this.container.dispatchEvent(customEvent);
    }
    
    highlightConnected(targetNode) {
        // 重置所有樣式
        this.nodes.select('circle')
            .style('opacity', 0.3)
            .attr('stroke-width', 2);
            
        this.links
            .style('opacity', 0.1);
            
        // 高亮目標節點
        this.nodes.filter(d => d.id === targetNode.id)
            .select('circle')
            .style('opacity', 1)
            .attr('stroke-width', 4);
            
        // 找到相關的連線和節點
        const connectedLinks = this.data.links.filter(link =>
            link.source.id === targetNode.id || link.target.id === targetNode.id
        );
        
        const connectedNodeIds = new Set();
        connectedLinks.forEach(link => {
            connectedNodeIds.add(link.source.id);
            connectedNodeIds.add(link.target.id);
        });
        
        // 高亮相關節點
        this.nodes.filter(d => connectedNodeIds.has(d.id))
            .select('circle')
            .style('opacity', 1);
            
        // 高亮相關連線
        this.links.filter(d =>
            d.source.id === targetNode.id || d.target.id === targetNode.id
        ).style('opacity', 0.8);
        
        // 3秒後恢復
        setTimeout(() => {
            this.resetHighlight();
        }, 3000);
    }
    
    resetHighlight() {
        this.nodes.select('circle')
            .style('opacity', 1)
            .attr('stroke-width', 2);
            
        this.links
            .style('opacity', 0.6);
    }
    
    centerGraph() {
        if (!this.data || !this.data.nodes.length) return;
        
        // 計算節點的邊界
        const xExtent = d3.extent(this.data.nodes, d => d.x);
        const yExtent = d3.extent(this.data.nodes, d => d.y);
        
        const width = xExtent[1] - xExtent[0];
        const height = yExtent[1] - yExtent[0];
        
        const midX = (xExtent[0] + xExtent[1]) / 2;
        const midY = (yExtent[0] + yExtent[1]) / 2;
        
        const scale = Math.min(
            this.width / width,
            this.height / height
        ) * 0.8;
        
        const translate = [
            this.width / 2 - scale * midX,
            this.height / 2 - scale * midY
        ];
        
        this.svg.transition()
            .duration(750)
            .call(
                d3.zoom().transform,
                d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale)
            );
    }
    
    getLinkColor(relationType) {
        const colors = {
            'symptom_to_cause': '#dc3545',
            'cause_to_treatment': '#28a745',
            'method_to_location': '#007bff',
            'same_category': '#6c757d',
            'co_occurrence': '#17a2b8'
        };
        return colors[relationType] || '#999';
    }
    
    getRelationLabel(relationType) {
        const labels = {
            'symptom_to_cause': '症→因',
            'cause_to_treatment': '因→治',
            'method_to_location': '法→位',
            'same_category': '同類',
            'co_occurrence': '共現'
        };
        return labels[relationType] || '';
    }
    
    // 導出圖片
    exportImage(format = 'png') {
        const svgElement = this.svg.node();
        const svgData = new XMLSerializer().serializeToString(svgElement);
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const img = new Image();
        
        canvas.width = this.width;
        canvas.height = this.height;
        
        img.onload = function() {
            ctx.fillStyle = 'white';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0);
            
            const link = document.createElement('a');
            link.download = `relation-graph.${format}`;
            link.href = canvas.toDataURL(`image/${format}`);
            link.click();
        };
        
        img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));
    }
    
    // 銷毀圖表
    destroy() {
        if (this.simulation) {
            this.simulation.stop();
        }
        if (this.tooltip) {
            this.tooltip.remove();
        }
        this.container.innerHTML = '';
    }
}

// 全域導出
window.RelationGraph = RelationGraph;
