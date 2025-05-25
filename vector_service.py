"""
向量搜尋服務模組
整合 Chroma 向量數據庫，提供語義搜尋功能
"""

import os
import logging
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import jieba
import re
from models import Session, Segment, db

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """搜尋結果數據類"""
    content_id: str
    content_type: str  # 'session' or 'segment'
    title: str
    content: str
    score: float
    metadata: Dict[str, Any]

class EmbeddingManager:
    """嵌入模型管理器"""
    
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """載入嵌入模型"""
        try:
            logger.info(f"正在載入嵌入模型: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("嵌入模型載入成功")
        except Exception as e:
            logger.error(f"載入嵌入模型失敗: {e}")
            # 回退到較小的中文模型
            fallback_model = "shibing624/text2vec-base-chinese"
            logger.info(f"嘗試載入回退模型: {fallback_model}")
            try:
                self.model = SentenceTransformer(fallback_model)
                self.model_name = fallback_model
                logger.info("回退模型載入成功")
            except Exception as e2:
                logger.error(f"回退模型也載入失敗: {e2}")
                raise e2
    
    def encode(self, texts: List[str]) -> List[List[float]]:
        """將文本編碼為向量"""
        if not self.model:
            raise RuntimeError("嵌入模型未載入")
        
        # 預處理文本
        processed_texts = [self._preprocess_text(text) for text in texts]
        
        try:
            embeddings = self.model.encode(processed_texts, normalize_embeddings=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"文本編碼失敗: {e}")
            raise
    
    def _preprocess_text(self, text: str) -> str:
        """預處理文本"""
        if not text:
            return ""
        
        # 移除過多的空白字符
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 限制長度，避免過長文本影響性能
        if len(text) > 512:
            text = text[:512]
        
        return text


class ChromaManager:
    """Chroma 向量數據庫管理器"""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.persist_directory = persist_directory
        self.client = None
        self.collection = None
        self.embedding_manager = EmbeddingManager()
        self._init_client()
    
    def _init_client(self):
        """初始化 Chroma 客戶端"""
        try:
            # 確保持久化目錄存在
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # 初始化 Chroma 客戶端
            self.client = chromadb.PersistentClient(path=self.persist_directory)
            
            # 獲取或創建集合
            self.collection = self.client.get_or_create_collection(
                name="knowledge_base",
                metadata={"description": "知識管理系統的語義搜尋集合"}
            )
            
            logger.info(f"Chroma 客戶端初始化成功，集合大小: {self.collection.count()}")
            
        except Exception as e:
            logger.error(f"Chroma 客戶端初始化失敗: {e}")
            raise
    
    def add_session(self, session: Session):
        """添加課程到向量數據庫"""
        if not session.overview:
            return
        
        try:
            # 準備文檔數據
            doc_id = f"session_{session.id}"
            content = f"{session.title}\n\n{session.overview}"
            
            # 準備元數據
            metadata = {
                "type": "session",
                "session_id": session.id,
                "title": session.title,
                "date": session.date.isoformat() if session.date else None,
                "tags": ",".join([tag.name for tag in session.tags]),
                "tag_categories": ",".join([tag.category for tag in session.tags])
            }
            
            # 生成嵌入向量
            embeddings = self.embedding_manager.encode([content])
            
            # 添加到 Chroma
            self.collection.upsert(
                ids=[doc_id],
                embeddings=embeddings,
                documents=[content],
                metadatas=[metadata]
            )
            
            logger.info(f"課程 {session.id} 已添加到向量數據庫")
            
        except Exception as e:
            logger.error(f"添加課程到向量數據庫失敗: {e}")
    
    def add_segment(self, segment: Segment):
        """添加段落到向量數據庫"""
        if not segment.content:
            return
        
        try:
            # 準備文檔數據
            doc_id = f"segment_{segment.id}"
            content = f"{segment.title or ''}\n\n{segment.content}"
            
            # 準備元數據
            metadata = {
                "type": "segment",
                "segment_id": segment.id,
                "session_id": segment.session_id,
                "segment_type": segment.segment_type,
                "title": segment.title or "",
                "session_title": segment.session.title if segment.session else "",
                "tags": ",".join([tag.name for tag in segment.tags]),
                "tag_categories": ",".join([tag.category for tag in segment.tags])
            }
            
            # 生成嵌入向量
            embeddings = self.embedding_manager.encode([content])
            
            # 添加到 Chroma
            self.collection.upsert(
                ids=[doc_id],
                embeddings=embeddings,
                documents=[content],
                metadatas=[metadata]
            )
            
            logger.info(f"段落 {segment.id} 已添加到向量數據庫")
            
        except Exception as e:
            logger.error(f"添加段落到向量數據庫失敗: {e}")
    
    def remove_session(self, session_id: int):
        """從向量數據庫移除課程"""
        try:
            doc_id = f"session_{session_id}"
            self.collection.delete(ids=[doc_id])
            logger.info(f"課程 {session_id} 已從向量數據庫移除")
        except Exception as e:
            logger.error(f"移除課程失敗: {e}")
    
    def remove_segment(self, segment_id: int):
        """從向量數據庫移除段落"""
        try:
            doc_id = f"segment_{segment_id}"
            self.collection.delete(ids=[doc_id])
            logger.info(f"段落 {segment_id} 已從向量數據庫移除")
        except Exception as e:
            logger.error(f"移除段落失敗: {e}")
    
    def semantic_search(self, query: str, limit: int = 10, 
                       content_type: Optional[str] = None) -> List[SearchResult]:
        """語義搜尋"""
        try:
            # 生成查詢向量
            query_embeddings = self.embedding_manager.encode([query])
            
            # 準備搜尋條件
            where_conditions = {}
            if content_type:
                where_conditions["type"] = content_type
            
            # 執行搜尋
            results = self.collection.query(
                query_embeddings=query_embeddings,
                n_results=limit,
                where=where_conditions if where_conditions else None
            )
            
            # 轉換結果格式
            search_results = []
            if results['ids'] and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    metadata = results['metadatas'][0][i]
                    distance = results['distances'][0][i] if results['distances'] and results['distances'][0] else 0.0
                    score = 1 - distance  # 轉換為相似度分數
                    
                    result = SearchResult(
                        content_id=doc_id,
                        content_type=metadata.get('type', 'unknown'),
                        title=metadata.get('title', ''),
                        content=results['documents'][0][i] if results['documents'] else '',
                        score=score,
                        metadata=metadata
                    )
                    search_results.append(result)
            
            logger.info(f"語義搜尋完成，找到 {len(search_results)} 個結果")
            return search_results
            
        except Exception as e:
            logger.error(f"語義搜尋失敗: {e}")
            return []
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """獲取集合統計信息"""
        try:
            count = self.collection.count()
            return {
                "total_documents": count,
                "model_name": self.embedding_manager.model_name,
                "persist_directory": self.persist_directory
            }
        except Exception as e:
            logger.error(f"獲取統計信息失敗: {e}")
            return {}


class HybridSearchEngine:
    """混合搜尋引擎：結合關鍵字搜尋和語義搜尋"""
    
    def __init__(self, chroma_manager: ChromaManager):
        self.chroma_manager = chroma_manager
    
    def search(self, query: str, search_type: str = "hybrid", 
               limit: int = 10) -> List[Dict[str, Any]]:
        """
        混合搜尋
        
        Args:
            query: 搜尋查詢
            search_type: 搜尋類型 ("semantic", "keyword", "hybrid")
            limit: 結果限制
        """
        results = []
        
        if search_type in ["semantic", "hybrid"]:
            # 語義搜尋
            semantic_results = self.chroma_manager.semantic_search(query, limit)
            for result in semantic_results:
                results.append({
                    "type": "semantic",
                    "score": result.score,
                    "content_type": result.content_type,
                    "content_id": result.content_id,
                    "title": result.title,
                    "content": result.content[:200] + "..." if len(result.content) > 200 else result.content,
                    "metadata": result.metadata
                })
        
        if search_type in ["keyword", "hybrid"]:
            # 關鍵字搜尋（使用現有的 SQL 搜尋）
            keyword_results = self._keyword_search(query, limit)
            for result in keyword_results:
                results.append({
                    "type": "keyword",
                    "score": result.get("score", 0.5),
                    "content_type": result["type"],
                    "content_id": result["id"],
                    "title": result["title"],
                    "content": result["content"],
                    "metadata": result.get("metadata", {})
                })
        
        # 去重和排序
        if search_type == "hybrid":
            results = self._merge_and_rank_results(results)
        
        return results[:limit]
    
    def _keyword_search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """關鍵字搜尋（基於現有的 SQL 搜尋）"""
        results = []
        
        try:
            # 搜尋課程
            sessions = Session.query.filter(
                Session.title.contains(query) | 
                Session.overview.contains(query)
            ).limit(limit // 2).all()
            
            for session in sessions:
                results.append({
                    "type": "session",
                    "id": f"session_{session.id}",
                    "title": session.title,
                    "content": session.overview or "",
                    "score": 0.8,
                    "metadata": {
                        "session_id": session.id,
                        "date": session.date.isoformat() if session.date else None
                    }
                })
            
            # 搜尋段落
            segments = Segment.query.filter(
                Segment.title.contains(query) | 
                Segment.content.contains(query)
            ).limit(limit // 2).all()
            
            for segment in segments:
                results.append({
                    "type": "segment",
                    "id": f"segment_{segment.id}",
                    "title": segment.title or "",
                    "content": segment.content or "",
                    "score": 0.7,
                    "metadata": {
                        "segment_id": segment.id,
                        "session_id": segment.session_id,
                        "session_title": segment.session.title if segment.session else ""
                    }
                })
            
        except Exception as e:
            logger.error(f"關鍵字搜尋失敗: {e}")
        
        return results
    
    def _merge_and_rank_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合併和排序混合搜尋結果"""
        # 簡單的去重邏輯：基於 content_id
        seen_ids = set()
        merged_results = []
        
        # 按分數排序
        results.sort(key=lambda x: x["score"], reverse=True)
        
        for result in results:
            content_id = result["content_id"]
            if content_id not in seen_ids:
                seen_ids.add(content_id)
                merged_results.append(result)
        
        return merged_results


# 全局實例（單例模式）
_chroma_manager: Optional[ChromaManager] = None
_hybrid_search_engine: Optional[HybridSearchEngine] = None

def get_chroma_manager() -> ChromaManager:
    """獲取 Chroma 管理器實例"""
    global _chroma_manager
    if _chroma_manager is None:
        _chroma_manager = ChromaManager()
    return _chroma_manager

def get_hybrid_search_engine() -> HybridSearchEngine:
    """獲取混合搜尋引擎實例"""
    global _hybrid_search_engine
    if _hybrid_search_engine is None:
        _hybrid_search_engine = HybridSearchEngine(get_chroma_manager())
    return _hybrid_search_engine

def initialize_vector_db():
    """初始化向量數據庫"""
    try:
        logger.info("開始初始化向量數據庫...")
        chroma_manager = get_chroma_manager()
        
        # 同步現有數據
        sync_existing_data()
        
        logger.info("向量數據庫初始化完成")
        return True
    except Exception as e:
        logger.error(f"向量數據庫初始化失敗: {e}")
        return False

def sync_existing_data():
    """同步現有數據到向量數據庫"""
    try:
        logger.info("開始同步現有數據...")
        chroma_manager = get_chroma_manager()
        
        # 同步所有課程
        sessions = Session.query.all()
        for session in sessions:
            if session.overview:
                chroma_manager.add_session(session)
        
        # 同步所有段落
        segments = Segment.query.all()
        for segment in segments:
            if segment.content:
                chroma_manager.add_segment(segment)
        
        logger.info(f"數據同步完成，處理了 {len(sessions)} 個課程和 {len(segments)} 個段落")
        
    except Exception as e:
        logger.error(f"數據同步失敗: {e}")
