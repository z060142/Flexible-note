import logging
from sqlalchemy import or_, func # Removed 'and_' as it's not used in UnifiedSearchService

# Assuming models.py is at the root or accessible in PYTHONPATH
from models import Session, Segment, Tag 
# Assuming vector_service.py is at the root or accessible in PYTHONPATH
try:
    from vector_service import get_hybrid_search_engine, VECTOR_SEARCH_ENABLED
except ImportError as e:
    # Fallback for when vector_service is not available (e.g., in a different environment)
    logging.getLogger(__name__).warning(f"Vector search service import failed in search_service: {e}")
    VECTOR_SEARCH_ENABLED = False
    def get_hybrid_search_engine():
        logging.getLogger(__name__).error("get_hybrid_search_engine called but vector search is disabled in search_service.")
        class MockSearchEngine:
            def search(self, query, strategy, limit):
                logging.getLogger(__name__).error(f"MockSearchEngine.search called with query: {query}, strategy: {strategy}, limit: {limit}")
                return []
        return MockSearchEngine()

logger = logging.getLogger(__name__)

class UnifiedSearchService:
    """無感知的智能搜尋服務 - 自動決定最佳搜尋策略"""
    
    def __init__(self):
        self.vector_enabled = VECTOR_SEARCH_ENABLED
        if self.vector_enabled:
            try:
                self.search_engine = get_hybrid_search_engine()
                if self.search_engine is None: # Check if mock was returned
                    logger.warning("Hybrid search engine is None, vector search might not function correctly.")
                    self.vector_enabled = False
            except Exception as e:
                logger.warning(f"向量搜尋引擎初始化失敗: {e}")
                self.vector_enabled = False
    
    def search(self, query, context=None, limit=10, **kwargs):
        if not query or not query.strip():
            return {
                'results': [], 'total_count': 0, 'search_strategy': 'none', 'query': query
            }
        
        query = query.strip()
        search_strategy = self._determine_search_strategy(query, context)
        
        try:
            if search_strategy == 'vector_enhanced' and self.vector_enabled and self.search_engine:
                results = self._vector_enhanced_search(query, limit, **kwargs)
            elif search_strategy == 'vector_primary' and self.vector_enabled and self.search_engine:
                results = self._vector_primary_search(query, limit, **kwargs)
            else: # Fallback to traditional if vector is not enabled or engine is missing
                search_strategy = 'traditional' # Ensure strategy reflects actual search
                results = self._traditional_search(query, limit, **kwargs)
            
            formatted_results = self._format_unified_results(results, search_strategy)
            
            return {
                'results': formatted_results, 'total_count': len(formatted_results),
                'search_strategy': search_strategy, 'query': query, 'vector_enabled': self.vector_enabled
            }
        except Exception as e:
            logger.error(f"搜尋失敗: {e}")
            try:
                results = self._traditional_search(query, limit, **kwargs)
                formatted_results = self._format_unified_results(results, 'traditional_fallback')
                return {
                    'results': formatted_results, 'total_count': len(formatted_results),
                    'search_strategy': 'traditional_fallback', 'query': query, 'error': str(e)
                }
            except Exception as fallback_error:
                logger.error(f"傳統搜尋也失敗: {fallback_error}")
                return {
                    'results': [], 'total_count': 0, 'search_strategy': 'error',
                    'query': query, 'error': str(fallback_error)
                }

    def _determine_search_strategy(self, query, context):
        if not self.vector_enabled: return 'traditional'
        query_length = len(query)
        word_count = len(query.split())
        if word_count <= 2 and query_length <= 10: return 'vector_enhanced'
        elif word_count > 5 or query_length > 20: return 'vector_primary'
        else:
            return 'vector_enhanced' if context in ['quick_search', 'tag_search'] else 'vector_primary'

    def _vector_enhanced_search(self, query, limit, **kwargs):
        try:
            traditional_results = self._traditional_search(query, limit // 2 if limit > 1 else 1, **kwargs) # Ensure limit is at least 1
            # Ensure search_engine is not None before calling search
            vector_results = self.search_engine.search(query, 'semantic', limit // 2 if limit > 1 else 1) if self.search_engine else []

            combined_results = self._merge_results(traditional_results, vector_results)
            return combined_results[:limit]
        except Exception as e:
            logger.warning(f"向量增強搜尋失敗，降級到傳統搜尋: {e}")
            return self._traditional_search(query, limit, **kwargs)

    def _vector_primary_search(self, query, limit, **kwargs):
        try:
            # Ensure search_engine is not None before calling search
            vector_results = self.search_engine.search(query, 'hybrid', limit) if self.search_engine else []
            
            if len(vector_results) < limit // 2:
                traditional_limit = limit - len(vector_results)
                traditional_results = self._traditional_search(query, traditional_limit, **kwargs)
                return self._merge_results(vector_results, traditional_results)
            return vector_results
        except Exception as e:
            logger.warning(f"向量主導搜尋失敗，降級到傳統搜尋: {e}")
            return self._traditional_search(query, limit, **kwargs)

    def _traditional_search(self, query, limit, **kwargs):
        results = []
        # Ensure limit is at least 0 for queries
        query_limit_session = max(0, limit // 2 if limit > 1 else (1 if limit == 1 else 0))
        query_limit_segment = max(0, limit - query_limit_session)


        if query_limit_session > 0:
            sessions = Session.query.filter(or_(Session.title.contains(query), Session.overview.contains(query))).limit(query_limit_session).all()
            for session_item in sessions: # Renamed to avoid conflict
                results.append({
                    'type': 'traditional', 'content_type': 'session', 'title': session_item.title,
                    'content': session_item.overview or '', 'score': 0.8,
                    'metadata': {
                        'session_id': session_item.id, 'date': session_item.date.isoformat() if session_item.date else None,
                        'tags': ','.join([tag.name for tag in session_item.tags])
                    }
                })
        
        if query_limit_segment > 0:
            segments = Segment.query.filter(or_(Segment.title.contains(query), Segment.content.contains(query))).join(Session).limit(query_limit_segment).all()
            for segment_item in segments: # Renamed to avoid conflict
                results.append({
                    'type': 'traditional', 'content_type': 'segment', 'title': segment_item.title or f'段落 {segment_item.id}',
                    'content': segment_item.content or '', 'score': 0.7,
                    'metadata': {
                        'segment_id': segment_item.id, 'session_id': segment_item.session_id,
                        'session_title': segment_item.session.title if segment_item.session else '',
                        'tags': ','.join([tag.name for tag in segment_item.tags])
                    }
                })
        
        # Tag-based search can add a few more results if limit is not reached
        if len(results) < limit:
            tags_found = Tag.query.filter(Tag.name.contains(query)).limit(5).all() # Renamed to avoid conflict
            for tag_item in tags_found: 
                # How many more results can we add?
                remaining_limit = limit - len(results)
                if remaining_limit <= 0: break

                tagged_segments = Segment.query.join(Segment.tags).filter(Tag.id == tag_item.id).limit(max(1, remaining_limit)).all() # Fetch at least 1, up to remaining
                for segment_item in tagged_segments: # Renamed
                    if len(results) >= limit: break
                    results.append({
                        'type': 'traditional', 'content_type': 'segment', 'title': segment_item.title or f'段落 {segment_item.id}',
                        'content': segment_item.content or '', 'score': 0.6,
                        'metadata': {
                            'segment_id': segment_item.id, 'session_id': segment_item.session_id,
                            'session_title': segment_item.session.title if segment_item.session else '',
                            'tags': ','.join([t.name for t in segment_item.tags]), 'matched_tag': tag_item.name
                        }
                    })
        return results[:limit] # Ensure final list does not exceed limit

    def _merge_results(self, results1, results2):
        seen_items = set()
        merged_results = []
        for result in results1:
            key = self._get_result_key(result)
            if key not in seen_items: seen_items.add(key); merged_results.append(result)
        for result in results2:
            key = self._get_result_key(result)
            if key not in seen_items: seen_items.add(key); merged_results.append(result)
        merged_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        return merged_results

    def _get_result_key(self, result):
        if result.get('content_type') == 'session': return f"session_{result.get('metadata', {}).get('session_id')}"
        elif result.get('content_type') == 'segment': return f"segment_{result.get('metadata', {}).get('segment_id')}"
        else: return f"other_{hash(result.get('title', '') + result.get('content', '')[:50])}"

    def _format_unified_results(self, results, search_strategy):
        formatted_results = []
        for result in results:
            formatted_result = {
                'content_type': result.get('content_type'), 'title': result.get('title'),
                'content_preview': (result.get('content', '')[:200] + '...') if len(result.get('content', '')) > 200 else result.get('content', ''),
                'score': result.get('score', 0), 'search_type': result.get('type', search_strategy),
                'metadata': result.get('metadata', {})
            }
            if result.get('content_type') == 'session':
                formatted_result['session_id'] = result['metadata'].get('session_id')
                formatted_result['session_title'] = result.get('title')
            elif result.get('content_type') == 'segment':
                formatted_result['segment_id'] = result['metadata'].get('segment_id')
                formatted_result['session_id'] = result['metadata'].get('session_id')
                formatted_result['session_title'] = result['metadata'].get('session_title', '')
                formatted_result['segment_title'] = result.get('title')
            formatted_results.append(formatted_result)
        return formatted_results
