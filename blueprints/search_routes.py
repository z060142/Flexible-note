import logging
import re # For extract_keywords
from flask import Blueprint, request, jsonify, render_template
from sqlalchemy import or_, and_, func

from models import db, Session, Segment, Tag, QueryRelation, segment_tags # segment_tags is a table, not a model
from config import CATEGORY_COLORS # Required by execute_smart_search, build_relation_graph (placeholder)

# Initialize logger
logger = logging.getLogger(__name__)

# Import vector search related services safely (used by helper functions, not directly by UnifiedSearchService anymore here)
try:
    from vector_service import get_chroma_manager, get_hybrid_search_engine, VECTOR_SEARCH_ENABLED
except ImportError as e:
    logger.warning(f"Vector search service import failed in search_routes.py: {e}")
    # Mock functions might still be needed if helper functions call them, though ideally, they shouldn't
    VECTOR_SEARCH_ENABLED = False 
    def get_chroma_manager():
        logger.error("Mock get_chroma_manager called from search_routes.py")
        return None
    def get_hybrid_search_engine():
        logger.error("Mock get_hybrid_search_engine called from search_routes.py")
        class MockSearchEngine:
             def search(self, query, strategy, limit): return []
        return MockSearchEngine()

from services.search_service import UnifiedSearchService

search_bp = Blueprint('search', __name__)
unified_search = UnifiedSearchService()


# Placeholder for build_relation_graph
def build_relation_graph(start_point, depth=2):
    logger.info(f"Placeholder build_relation_graph called with start_point: {start_point}, depth: {depth}")
    return {'nodes': [], 'links': [], 'message': 'Not implemented in this blueprint yet'}

# Helper functions (smart_tag_matching, extract_keywords, etc.) remain here as they are route-specific logic
# and not part of the UnifiedSearchService class itself.
# Copied helper functions
def smart_tag_matching(query, context):
    matched_tags_list = [] # Renamed to avoid conflict
    exact_matches = Tag.query.filter(Tag.name.ilike(f'%{query}%')).all()
    if context == 'symptom_to_cause':
        preferred_categories = ['症狀', '位置', '施術位置', '治療位置']
        exact_matches = [tag for tag in exact_matches if tag.category in preferred_categories]
    elif context == 'cause_to_treatment':
        preferred_categories = ['病因', '手法', '治療']
        exact_matches = [tag for tag in exact_matches if tag.category in preferred_categories]
    elif context == 'method_analysis':
        preferred_categories = ['手法', '治療']
        exact_matches = [tag for tag in exact_matches if tag.category in preferred_categories]
    matched_tags_list.extend(exact_matches[:5])
    if len(matched_tags_list) < 3:
        keywords = extract_keywords(query)
        for keyword in keywords:
            if len(keyword) >= 2:
                semantic_matches = Tag.query.filter(Tag.name.contains(keyword)).limit(3).all()
                for tag_item in semantic_matches: # Renamed to avoid conflict
                    if tag_item not in matched_tags_list: matched_tags_list.append(tag_item)
    if matched_tags_list:
        tag_usage = {tag.id: db.session.query(func.count(segment_tags.c.tag_id)).filter(segment_tags.c.tag_id == tag.id).scalar() or 0 for tag in matched_tags_list}
        matched_tags_list.sort(key=lambda x: tag_usage.get(x.id, 0), reverse=True)
    return matched_tags_list[:5]

def extract_keywords(query):
    stop_words = {'的', '了', '是', '在', '有', '和', '與', '或', '但', '會', '能', '可以', '應該', '需要'}
    keywords = []
    parts = re.split(r'[，。！？、\s]+', query)
    for part in parts:
        if part and len(part) >= 2 and part not in stop_words:
            keywords.append(part)
            if len(part) > 3:
                for i in range(len(part) - 1):
                    sub = part[i:i+2]
                    if sub not in stop_words: keywords.append(sub)
    return list(set(keywords))

def execute_smart_search(matched_tags, context, original_query):
    if not matched_tags: return []
    results = []
    matched_tag_ids = [tag.id for tag in matched_tags]
    if context == 'symptom_to_cause':
        query_db = db.session.query(Segment).distinct().join(Segment.tags).filter(Tag.id.in_(matched_tag_ids))
        found_segments = query_db.all()
        for segment in found_segments:
            potential_cause_tags, matched_symptoms = [], []
            for tag in segment.tags:
                if tag.category == '病因': potential_cause_tags.append(tag.to_dict())
                if tag.id in matched_tag_ids: matched_symptoms.append(tag.to_dict())
            if segment.session:
                for tag in segment.session.tags:
                    if tag.category == '病因' and not any(pct['id'] == tag.id for pct in potential_cause_tags):
                        potential_cause_tags.append(tag.to_dict())
            if potential_cause_tags or matched_symptoms:
                results.append({
                    "segment_id": segment.id, "segment_title": segment.title,
                    "segment_content_preview": (segment.content[:100] + "...") if segment.content else "",
                    "session_id": segment.session_id, "session_title": segment.session.title if segment.session else "N/A",
                    "potential_cause_tags": potential_cause_tags, "matched_symptoms": matched_symptoms,
                    "search_type": "smart_symptom_diagnosis"
                })
    elif context == 'cause_to_treatment':
        query_db = db.session.query(Segment).distinct().join(Segment.tags).filter(Tag.id.in_(matched_tag_ids))
        found_segments = query_db.all()
        for segment in found_segments:
            potential_treatment_tags, matched_causes = [], []
            for tag in segment.tags:
                if tag.category in ['治療', '手法']: potential_treatment_tags.append(tag.to_dict())
                if tag.id in matched_tag_ids: matched_causes.append(tag.to_dict())
            if potential_treatment_tags or segment.segment_type == '治療' or matched_causes:
                results.append({
                    "segment_id": segment.id, "segment_title": segment.title,
                    "segment_content_preview": (segment.content[:100] + "...") if segment.content else "",
                    "segment_type": segment.segment_type, "session_id": segment.session_id,
                    "session_title": segment.session.title if segment.session else "N/A",
                    "potential_treatment_tags": potential_treatment_tags, "matched_causes": matched_causes,
                    "search_type": "smart_treatment_search"
                })
    elif context == 'method_analysis':
        method_tags_list = [tag for tag in matched_tags if tag.category in ['手法', '治療']] # Renamed
        if method_tags_list:
            method_tag = method_tags_list[0]
            segments_using_method = Segment.query.join(Segment.tags).filter(Tag.id == method_tag.id).all()
            unique_symptom_tags, unique_cause_tags, unique_location_tags = {}, {}, {}
            for seg in segments_using_method:
                for tag in seg.tags:
                    if tag.category == '症狀': unique_symptom_tags[tag.id] = tag
                    elif tag.category == '病因': unique_cause_tags[tag.id] = tag
                    elif tag.category in ['位置', '施術位置', '治療位置']: unique_location_tags[tag.id] = tag
            results.append({
                "method_name": method_tag.name, "method_id": method_tag.id, "description": method_tag.description,
                "applicable_symptoms": [t.to_dict() for t in unique_symptom_tags.values()],
                "treated_causes": [t.to_dict() for t in unique_cause_tags.values()],
                "common_locations": [t.to_dict() for t in unique_location_tags.values()],
                "example_segments": [{"segment_id": s.id, "segment_title": s.title, "session_id": s.session_id, "session_title": s.session.title if s.session else "N/A"} for s in segments_using_method[:5]],
                "search_type": "smart_method_analysis"
            })
        else: # Fallback for general search if no method tags found
            query_db = db.session.query(Segment).distinct().join(Segment.tags).filter(Tag.id.in_(matched_tag_ids))
            found_segments = query_db.all()
            for segment in found_segments:
                matched_tags_info = [tag.to_dict() for tag in segment.tags if tag.id in matched_tag_ids]
                if matched_tags_info:
                    results.append({
                        "segment_id": segment.id, "segment_title": segment.title,
                        "segment_content_preview": (segment.content[:100] + "...") if segment.content else "",
                        "session_id": segment.session_id, "session_title": segment.session.title if segment.session else "N/A",
                        "matched_tags": matched_tags_info, "search_type": "smart_general_search"
                    })
    return results

def get_search_suggestions_for_context(context):
    suggestions = []
    if context == 'symptom_to_cause':
        common_symptoms = Tag.query.filter(Tag.category == '症狀').outerjoin(segment_tags, Tag.id == segment_tags.c.tag_id).group_by(Tag.id).order_by(func.count(segment_tags.c.tag_id).desc()).limit(5).all()
        suggestions = [tag.name for tag in common_symptoms]
    elif context == 'cause_to_treatment':
        common_causes = Tag.query.filter(Tag.category == '病因').outerjoin(segment_tags, Tag.id == segment_tags.c.tag_id).group_by(Tag.id).order_by(func.count(segment_tags.c.tag_id).desc()).limit(5).all()
        suggestions = [tag.name for tag in common_causes]
    elif context == 'method_analysis':
        common_methods = Tag.query.filter(Tag.category == '手法').outerjoin(segment_tags, Tag.id == segment_tags.c.tag_id).group_by(Tag.id).order_by(func.count(segment_tags.c.tag_id).desc()).limit(5).all()
        suggestions = [tag.name for tag in common_methods]
    return suggestions

# Moved Flask Routes
@search_bp.route('/api/search/unified', methods=['POST'])
def unified_search_api():
    try:
        data = request.get_json()
        if not data: return jsonify({'results': [], 'message': 'No search data provided'})
        query = data.get('query', '')
        context = data.get('context', 'general_search')
        limit = data.get('limit', 10)
        if not query.strip(): return jsonify({'results': [], 'message': 'Please provide a search query'})
        search_results = unified_search.search(query=query, context=context, limit=limit)
        return jsonify(search_results)
    except Exception as e:
        logger.error(f"統一搜尋失敗: {e}")
        return jsonify({'results': [], 'total_count': 0, 'search_strategy': 'error', 'query': data.get('query', ''), 'error': str(e)}), 500

@search_bp.route('/api/search/semantic', methods=['POST'])
def semantic_search(): # Legacy
    try:
        data = request.get_json()
        if not data: return jsonify({'results': [], 'message': 'No search data provided'})
        query = data.get('query', '')
        limit = data.get('limit', 10)
        search_results = unified_search.search(query=query, context='semantic_search', limit=limit) # Use unified_search
        # Format for backward compatibility
        formatted_results = []
        for result in search_results['results']:
            formatted_result = {
                'search_type': result['search_type'], 'score': result['score'],
                'content_type': result['content_type'], 'title': result['title'],
                'content_preview': result['content_preview'], 'metadata': result['metadata']
            }
            if result['content_type'] == 'session':
                formatted_result['session_id'] = result.get('session_id')
                formatted_result['session_title'] = result.get('session_title')
            elif result['content_type'] == 'segment':
                formatted_result['segment_id'] = result.get('segment_id')
                formatted_result['session_id'] = result.get('session_id')
                formatted_result['session_title'] = result.get('session_title', '')
                formatted_result['segment_title'] = result.get('segment_title')
            formatted_results.append(formatted_result)
        return jsonify({
            'results': formatted_results, 'query': search_results['query'],
            'search_type': search_results['search_strategy'], 'total_count': search_results['total_count']
        })
    except Exception as e:
        logger.error(f"語義搜尋失敗: {e}")
        return jsonify({'error': str(e)}), 500

@search_bp.route('/api/search/suggestions', methods=['GET'])
def search_suggestions():
    try:
        query = request.args.get('q', '').strip()
        if len(query) < 2: return jsonify([])
        tag_suggestions = Tag.query.filter(Tag.name.contains(query)).limit(5).all()
        suggestions = [{'text': tag.name, 'type': 'tag', 'category': tag.category, 'color': tag.color} for tag in tag_suggestions]
        session_suggestions = Session.query.filter(Session.title.contains(query)).limit(3).all()
        suggestions.extend([{'text': session.title, 'type': 'session', 'id': session.id} for session in session_suggestions])
        return jsonify(suggestions)
    except Exception as e:
        logger.error(f"Search suggestions error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@search_bp.route('/api/search/smart', methods=['POST'])
def smart_search():
    try:
        data = request.get_json()
        if not data: return jsonify({'results': [], 'message': 'No search data provided'})
        query = data.get('query', '').strip()
        context = data.get('context', '')
        if not query: return jsonify({'results': [], 'message': 'Please provide a search query'})
        
        matched_tags_list = smart_tag_matching(query, context) # Renamed variable
        if not matched_tags_list:
            return jsonify({'results': [], 'message': f'找不到與 "{query}" 相關的標籤。請嘗試更具體的關鍵詞。', 'suggestions': get_search_suggestions_for_context(context)})
        
        results = execute_smart_search(matched_tags_list, context, query) # Use renamed variable
        return jsonify({'results': results, 'matched_tags': [tag.to_dict() for tag in matched_tags_list], 'query': query, 'context': context})
    except Exception as e:
        logger.error(f"智能搜索失敗: {e}")
        return jsonify({'error': str(e)}), 500

@search_bp.route('/search', methods=['GET', 'POST'])
def search(): # Older search page and logic
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data: return jsonify({'results': [], 'message': 'No search data provided'})
            query_type = data.get('query_type', 'symptom_to_cause')
            results = []
            if query_type == 'symptom_to_cause':
                symptom_tag_names = data.get('symptom_tags', [])
                location_name = data.get('location', None)
                if not symptom_tag_names: return jsonify({'results': [], 'message': 'Please provide at least one symptom tag.'})
                query_db = db.session.query(Segment).distinct().join(Segment.tags).filter(Tag.category == '症狀', Tag.name.in_(symptom_tag_names))
                if location_name: query_db = query_db.filter(Segment.tags.any(and_(Tag.category == '位置', Tag.name.contains(location_name))))
                found_segments = query_db.all()
                for segment in found_segments:
                    potential_cause_tags, matched_symptoms_on_segment = [], []
                    for tag_item in segment.tags: # Renamed
                        if tag_item.category == '病因': potential_cause_tags.append(tag_item.to_dict())
                        if tag_item.name in symptom_tag_names and tag_item.category == '症狀': matched_symptoms_on_segment.append(tag_item.to_dict())
                    if segment.session:
                        for tag_item in segment.session.tags: # Renamed
                            if tag_item.category == '病因' and not any(pct['id'] == tag_item.id for pct in potential_cause_tags): potential_cause_tags.append(tag_item.to_dict())
                    if potential_cause_tags:
                        results.append({"segment_id": segment.id, "segment_title": segment.title, "segment_content_preview": (segment.content[:100] + "...") if segment.content else "", "session_id": segment.session_id, "session_title": segment.session.title if segment.session else "N/A", "potential_cause_tags": potential_cause_tags, "matched_symptoms": matched_symptoms_on_segment})
            elif query_type == 'cause_to_treatment':
                cause_tag_names = data.get('cause_tags', [])
                preferred_domain_name = data.get('preferred_domain', None)
                if not cause_tag_names: return jsonify({'results': [], 'message': 'Please provide at least one cause tag.'})
                query_db = db.session.query(Segment).distinct().join(Segment.tags).filter(Tag.category == '病因', Tag.name.in_(cause_tag_names))
                if preferred_domain_name: query_db = query_db.join(Session, Segment.session_id == Session.id).filter(Session.tags.any(and_(Tag.category == '領域', Tag.name == preferred_domain_name)))
                found_segments = query_db.all()
                for segment in found_segments:
                    potential_treatment_tags, matched_causes_on_segment = [], []
                    for tag_item in segment.tags: # Renamed
                        if tag_item.category in ['治療', '手法']: potential_treatment_tags.append(tag_item.to_dict())
                        if tag_item.name in cause_tag_names and tag_item.category == '病因': matched_causes_on_segment.append(tag_item.to_dict())
                    if potential_treatment_tags or segment.segment_type == '治療':
                        results.append({"segment_id": segment.id, "segment_title": segment.title, "segment_content_preview": (segment.content[:100] + "...") if segment.content else "", "segment_type": segment.segment_type, "session_id": segment.session_id, "session_title": segment.session.title if segment.session else "N/A", "potential_treatment_tags": potential_treatment_tags, "matched_causes": matched_causes_on_segment})
            elif query_type == 'method_analysis':
                method_name = data.get('method_name', None)
                if not method_name: return jsonify({'results': [], 'message': 'Please provide a method name.'})
                method_tag = Tag.query.filter_by(name=method_name, category='手法').first()
                if not method_tag: return jsonify({'results': [], 'message': f"Method tag '{method_name}' not found."})
                segments_using_method = Segment.query.join(Segment.tags).filter(Tag.id == method_tag.id).all()
                unique_symptom_tags, unique_cause_tags, unique_cooccurring_methods, unique_location_tags = {}, {}, {}, {}
                for seg in segments_using_method:
                    for tag_item in seg.tags: # Renamed
                        if tag_item.category == '症狀': unique_symptom_tags[tag_item.id] = tag_item
                        elif tag_item.category == '病因': unique_cause_tags[tag_item.id] = tag_item
                        elif tag_item.category == '手法' and tag_item.id != method_tag.id: unique_cooccurring_methods[tag_item.id] = tag_item
                        elif tag_item.category == '位置': unique_location_tags[tag_item.id] = tag_item
                results.append({"method_name": method_tag.name, "method_id": method_tag.id, "description": method_tag.description, "applicable_symptoms": [t.to_dict() for t in unique_symptom_tags.values()], "treated_causes": [t.to_dict() for t in unique_cause_tags.values()], "common_locations": [t.to_dict() for t in unique_location_tags.values()], "related_methods": [t.to_dict() for t in unique_cooccurring_methods.values()], "example_segments": [{"segment_id": s.id, "segment_title": s.title, "session_id": s.session_id, "session_title": s.session.title if s.session else "N/A"} for s in segments_using_method[:5]]})
            elif query_type == 'relation_map':
                start_point = data.get('start_point', None)
                depth = data.get('depth', 2)
                if not start_point: return jsonify({'results': [], 'message': 'Please provide a start point.'})
                graph_data = build_relation_graph(start_point, depth) # Placeholder
                return jsonify(graph_data)
            return jsonify({'results': results})
        except Exception as e:
            logger.error(f"Search error in /search route: {str(e)}")
            return jsonify({'results': [], 'error': str(e)}), 500
    return render_template('search.html')
