import logging
from flask import Blueprint, request, jsonify
from models import db, Session, Segment, Tag # Added Session
from config import CATEGORY_COLORS

# Configure logger
logger = logging.getLogger(__name__)

# Import vector search related services safely
try:
    from vector_service import get_chroma_manager, VECTOR_SEARCH_ENABLED
except ImportError as e:
    logger.warning(f"Vector search service import failed: {e}")
    logger.warning("Proceeding with vector search disabled. Install chromadb and sentence-transformers if needed.")
    VECTOR_SEARCH_ENABLED = False
    # Mock function if import fails
    def get_chroma_manager():
        logger.error("get_chroma_manager called but vector search is disabled.")
        return None

segment_bp = Blueprint('segment', __name__)

# 新增段落
@segment_bp.route('/session/<int:session_id>/segment', methods=['POST'])
def add_segment(session_id):
    session = Session.query.get_or_404(session_id) # Requires Session model
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
            
        max_order = db.session.query(db.func.max(Segment.order_index)).filter_by(session_id=session_id).scalar() or 0
        
        segment = Segment(
            session_id=session_id,
            segment_type=data.get('segment_type', '內容'),
            title=data.get('title', ''),
            content=data.get('content', ''),
            order_index=max_order + 1
        )
        
        tag_data = data.get('tags', [])
        for tag_info in tag_data:
            if isinstance(tag_info, dict) and tag_info.get('name'):
                tag = Tag.query.filter_by(name=tag_info['name']).first()
                if not tag:
                    category = tag_info.get('category', '其他')
                    color = tag_info.get('color', CATEGORY_COLORS.get(category, '#6c757d'))
                    tag = Tag(
                        name=tag_info['name'],
                        category=category,
                        color=color
                    )
                    db.session.add(tag)
                    db.session.flush()  # 確保tag有ID
                segment.tags.append(tag)
        
        db.session.add(segment)
        db.session.commit()
        
        # 自動同步到向量數據庫（如果啟用）
        if VECTOR_SEARCH_ENABLED:
            try:
                chroma_manager = get_chroma_manager()
                chroma_manager.add_segment(segment)
            except Exception as e:
                logger.warning(f"向量數據庫同步失敗: {e}")
        
        return jsonify({'success': True, 'segment_id': segment.id})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding segment to session {session_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@segment_bp.route('/api/segment/<int:segment_id>', methods=['GET'])
def get_segment_detail(segment_id):
    try:
        segment = Segment.query.get(segment_id) 
        if not segment: 
            return jsonify({'error': 'Segment not found'}), 404
            
        segment_data = {
            'id': segment.id, 
            'session_id': segment.session_id,
            'segment_type': segment.segment_type, 
            'title': segment.title,
            'content': segment.content, 
            'tags': [tag.to_dict() for tag in segment.tags]
        }
        return jsonify(segment_data)
        
    except Exception as e:
        logger.error(f"Error getting segment detail for {segment_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@segment_bp.route('/api/segment/<int:segment_id>/update', methods=['POST']) 
def update_segment_detail(segment_id):
    try:
        segment = Segment.query.get(segment_id)
        if not segment: 
            return jsonify({'error': 'Segment not found'}), 404
            
        data = request.get_json()
        if not data: 
            return jsonify({'error': 'No input data provided'}), 400
            
        segment.segment_type = data.get('segment_type', segment.segment_type)
        segment.title = data.get('title', segment.title)
        segment.content = data.get('content', segment.content)
        
        if 'tags' in data: 
            segment.tags.clear()
            tag_data_list = data.get('tags', [])
            for tag_info in tag_data_list:
                if isinstance(tag_info, dict) and tag_info.get('name'):
                    tag_name = tag_info.get('name')
                    tag = Tag.query.filter_by(name=tag_name).first()
                    if not tag:
                        category = tag_info.get('category', '其他')
                        color = tag_info.get('color', CATEGORY_COLORS.get(category, '#6c757d'))
                        tag = Tag(name=tag_name, category=category, color=color)
                        db.session.add(tag)
                        db.session.flush()  # 確保tag有ID
                    segment.tags.append(tag)
                    
        db.session.commit()
        
        # 自動同步到向量數據庫（如果啟用）
        if VECTOR_SEARCH_ENABLED:
            try:
                chroma_manager = get_chroma_manager()
                chroma_manager.add_segment(segment)
            except Exception as e:
                logger.warning(f"向量數據庫同步失敗: {e}")
        
        return jsonify({'success': True, 'segment_id': segment.id})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating segment {segment_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@segment_bp.route('/api/segment/<int:segment_id>/delete', methods=['DELETE'])
def delete_segment_detail(segment_id):
    try:
        segment = Segment.query.get(segment_id)
        if not segment: 
            return jsonify({'error': 'Segment not found'}), 404
        
        # 從向量數據庫中刪除（如果啟用）
        if VECTOR_SEARCH_ENABLED:
            try:
                chroma_manager = get_chroma_manager()
                chroma_manager.delete_segment(segment_id)
            except Exception as e:
                logger.warning(f"向量數據庫刪除失敗: {e}")
                
        db.session.delete(segment)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Segment deleted'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting segment {segment_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500
