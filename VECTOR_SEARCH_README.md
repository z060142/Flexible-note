# 語義搜尋功能說明

## 概述

本系統整合了Chroma向量數據庫，提供基於AI的語義搜尋功能，能夠理解查詢的語義含義並找到最相關的內容。

## 主要特點

### 🧠 智能嵌入模型
- **主要模型**: BAAI/bge-m3 (BGE-M3)
  - 優秀的中文理解能力
  - 支持多語言
  - 高精度的語義向量表示
  
- **回退模型**: shibing624/text2vec-base-chinese
  - 較輕量的中文模型
  - 作為主模型載入失敗時的備選方案

### 🔍 三種搜尋模式

1. **語義搜尋** (Semantic Search)
   - 基於文本的語義含義
   - 能理解同義詞和相關概念
   - 適合概念性查詢

2. **關鍵字搜尋** (Keyword Search)
   - 基於精確的關鍵字匹配
   - 快速且準確
   - 適合已知術語的查詢

3. **混合搜尋** (Hybrid Search) **[推薦]**
   - 結合語義和關鍵字搜尋
   - 自動去重和排序
   - 提供最全面的搜尋結果

### 📚 支持的內容類型

- **課程概述** (Session Overview)
  - 課程標題和概述內容
  - 課程標籤和分類信息
  
- **課程段落** (Segment Content)
  - 段落標題和詳細內容
  - 段落類型和標籤信息

## 技術架構

### 核心組件

1. **EmbeddingManager** - 嵌入模型管理
   ```python
   # 自動載入BGE-M3模型，失敗時回退
   model = EmbeddingManager()
   embeddings = model.encode(["文本內容"])
   ```

2. **ChromaManager** - 向量數據庫管理
   ```python
   # 管理Chroma數據庫操作
   chroma = ChromaManager()
   chroma.add_session(session)  # 添加課程
   chroma.add_segment(segment)  # 添加段落
   ```

3. **HybridSearchEngine** - 混合搜尋引擎
   ```python
   # 執行混合搜尋
   engine = HybridSearchEngine(chroma)
   results = engine.search("查詢內容", "hybrid")
   ```

### 數據同步

系統會在以下操作時自動同步向量數據庫：
- ✅ 新增課程時
- ✅ 編輯課程時  
- ✅ 新增段落時
- ✅ 編輯段落時
- ✅ 刪除課程時
- ✅ 刪除段落時

### API端點

- `GET /semantic-search` - 語義搜尋頁面
- `POST /api/search/semantic` - 語義搜尋API
- `GET /api/vector/status` - 向量數據庫狀態
- `POST /api/vector/sync` - 手動同步數據

## 使用指南

### 基本使用

1. **訪問語義搜尋頁面**
   - 點擊導航欄中的 "🧠 語義搜尋"
   - 或直接訪問 `/semantic-search`

2. **輸入查詢**
   - 在搜尋框中輸入您想查找的內容
   - 支持自然語言查詢，例如：
     - "肩膀疼痛的治療方法"
     - "腰椎間盤突出症狀"
     - "頸部僵硬緩解技巧"

3. **選擇搜尋模式**
   - **混合搜尋**：最推薦，結合兩種方式
   - **語義搜尋**：理解語義含義
   - **關鍵字搜尋**：精確匹配關鍵字

4. **查看結果**
   - 結果按相關度排序
   - 顯示匹配分數和內容預覽
   - 可點擊查看完整內容

### 搜尋技巧

#### ✅ 良好的查詢示例
- "肩膀疼痛的原因和治療"
- "腰部不適的緩解方法"
- "頸椎問題的預防措施"
- "關節炎的症狀表現"

#### ❌ 避免的查詢方式
- 過於簡短："痛"
- 過於複雜："請告訴我所有關於人體解剖學的詳細信息包括骨骼肌肉神經系統的相互作用機制"

### 快速查詢按鈕

頁面提供了常用查詢的快速按鈕：
- 肩膀疼痛
- 腰椎問題  
- 頸部僵硬
- 關節炎治療
- 肌肉放鬆

## 系統要求

### 硬體要求
- **記憶體**: 至少 4GB RAM (推薦 8GB+)
- **存儲**: 額外 2-5GB 用於模型和向量數據
- **處理器**: 支持現代指令集的CPU

### 軟體依賴
- Python 3.11+
- chromadb >= 0.4.0
- sentence-transformers >= 2.2.0
- torch >= 2.0.0
- jieba >= 0.42.0

## 效能優化

### 模型載入優化
- 模型會在首次使用時載入，後續請求會復用
- 建議在系統啟動時預熱模型以減少首次查詢延遲

### 數據庫優化
- 向量數據庫使用持久化存儲，重啟後數據保留
- 大量數據同步時建議分批處理

### 查詢優化
- 限制查詢結果數量以提高響應速度
- 使用混合搜尋可以獲得最佳的查詢品質

## 故障排除

### 常見問題

1. **模型載入失敗**
   ```
   解決方案：
   - 檢查網路連接，確保能下載模型
   - 確認有足夠的磁碟空間
   - 系統會自動嘗試載入備用模型
   ```

2. **搜尋結果為空**
   ```
   解決方案：
   - 檢查是否有數據同步到向量數據庫
   - 嘗試手動同步：POST /api/vector/sync
   - 檢查向量數據庫狀態：GET /api/vector/status
   ```

3. **搜尋速度慢**
   ```
   解決方案：
   - 減少搜尋結果數量限制
   - 確保系統有足夠記憶體
   - 考慮升級硬體配置
   ```

### 檢查系統狀態

訪問 `/api/vector/status` 可以查看：
- 向量搜尋是否啟用
- 數據庫連接狀態
- 已索引的文檔數量
- 使用的嵌入模型

## 開發者指南

### 添加新的嵌入模型

在 `vector_service.py` 中修改 `EmbeddingManager`：

```python
def __init__(self, model_name: str = "your-new-model"):
    self.model_name = model_name
    # ... 其他代碼
```

### 自定義搜尋邏輯

繼承 `HybridSearchEngine` 類並重寫搜尋方法：

```python
class CustomSearchEngine(HybridSearchEngine):
    def search(self, query: str, search_type: str = "hybrid", limit: int = 10):
        # 自定義搜尋邏輯
        pass
```

### 批量數據同步

```python
from vector_service import sync_existing_data
sync_existing_data()  # 同步所有現有數據
```

## 未來規劃

- [ ] 支持更多嵌入模型選擇
- [ ] 添加搜尋結果的相關性反饋機制
- [ ] 實現增量索引更新
- [ ] 支持多模態搜尋（圖片+文字）
- [ ] 添加搜尋分析和統計功能

---

**技術支持**: 如遇問題請檢查系統日誌或聯繫開發者
