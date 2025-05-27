import os
import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
from datetime import datetime
from models import db, Session, Segment, Tag, Attachment
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

session_bp = Blueprint('session', __name__)

# 新增課程
@session_bp.route('/session/new', methods=['GET', 'POST'])
def new_session():
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            session = Session(
                title=data.get('title', ''),
                overview=data.get('overview', ''),
                date=datetime.fromisoformat(data.get('date', datetime.now().isoformat())) if data.get('date') else datetime.now()
            )
            
            tag_names = data.get('tags', [])
            for tag_name in tag_names:
                if tag_name.strip():  # 只處理非空標籤
                    tag = Tag.query.filter_by(name=tag_name.strip()).first()
                    if not tag:
                        tag = Tag(
                            name=tag_name.strip(), 
                            category=data.get('tag_category', '領域'),
                            color=CATEGORY_COLORS.get(data.get('tag_category', '領域'), '#6c757d')
                        )
                        db.session.add(tag)
                        db.session.flush()  # 確保tag有ID
                    session.tags.append(tag)
            
            db.session.add(session)
            db.session.commit()
            
            # 自動同步到向量數據庫（如果啟用）
            if VECTOR_SEARCH_ENABLED:
                try:
                    chroma_manager = get_chroma_manager()
                    chroma_manager.add_session(session)
                except Exception as e:
                    logger.warning(f"向量數據庫同步失敗: {e}")
            
            return jsonify({'success': True, 'session_id': session.id})
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating new session: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return render_template('session_form.html', datetime=datetime)

# 編輯課程
@session_bp.route('/session/<int:session_id>/edit', methods=['GET', 'POST'])
def edit_session(session_id):
    session = Session.query.get_or_404(session_id)
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
                
            session.title = data.get('title', session.title)
            session.overview = data.get('overview', session.overview)
            
            if data.get('date'):
                try:
                    session.date = datetime.fromisoformat(data.get('date'))
                except ValueError:
                    return jsonify({'success': False, 'error': 'Invalid date format'}), 400
                
            session.tags.clear() 
            tag_names = data.get('tags', [])
            tag_category = data.get('tag_category', '領域') 
            
            for tag_name in tag_names:
                if tag_name.strip():
                    tag = Tag.query.filter_by(name=tag_name.strip()).first()
                    if not tag:
                        tag = Tag(
                            name=tag_name.strip(), 
                            category=tag_category,
                            color=CATEGORY_COLORS.get(tag_category, '#6c757d')
                        )
                        db.session.add(tag)
                        db.session.flush()  # 確保tag有ID
                    session.tags.append(tag)
                
            db.session.commit()
            
            # 自動同步到向量數據庫（如果啟用）
            if VECTOR_SEARCH_ENABLED:
                try:
                    chroma_manager = get_chroma_manager()
                    chroma_manager.add_session(session)
                except Exception as e:
                    logger.warning(f"向量數據庫同步失敗: {e}")
            
            return jsonify({'success': True, 'session_id': session.id})
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error editing session {session_id}: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
        
    all_tags = Tag.query.all()
    return render_template('session_edit_form.html', session=session, all_tags=all_tags)

# 刪除課程
@session_bp.route('/session/<int:session_id>/delete', methods=['POST'])
def delete_session(session_id):
    session = Session.query.get_or_404(session_id)
    try:
        # Delete associated segments and their attachments
        for segment in session.segments:
            for attachment in segment.attachments:
                # Delete physical file
                try:
                    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], attachment.filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error deleting file {attachment.filename}: {str(e)}")
                db.session.delete(attachment)
            db.session.delete(segment)
        
        # 從向量數據庫中刪除（如果啟用）
        if VECTOR_SEARCH_ENABLED:
            try:
                chroma_manager = get_chroma_manager()
                chroma_manager.delete_session(session_id)
            except Exception as e:
                logger.warning(f"向量數據庫刪除失敗: {e}")
        
        db.session.delete(session)
        db.session.commit()
        return redirect(url_for('main.index')) # Assuming 'index' is in 'main_bp' now
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting session {session_id}: {str(e)}")
        return redirect(url_for('main.session_detail', session_id=session_id)) # Assuming 'session_detail' is in 'main_bp'

@session_bp.route('/api/session/<int:session_id>/export', methods=['GET'])
def export_session_json(session_id):
    try:
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404

        session_export_data = {
            'id': session.id,
            'title': session.title,
            'date': session.date.isoformat() if session.date else None,
            'overview': session.overview,
            'created_at': session.created_at.isoformat() if session.created_at else None,
            'updated_at': session.updated_at.isoformat() if session.updated_at else None,
            'tags': [tag.to_dict() for tag in session.tags],
            'segments': []
        }

        for segment in session.segments.order_by(Segment.order_index).all():
            segment_data = {
                'id': segment.id,
                'segment_type': segment.segment_type,
                'title': segment.title,
                'content': segment.content,
                'order_index': segment.order_index,
                'created_at': segment.created_at.isoformat() if segment.created_at else None,
                'tags': [tag.to_dict() for tag in segment.tags],
                'attachments': []
            }
            for att in segment.attachments:
                attachment_data = {
                    'id': att.id,
                    'filename': att.filename, 
                    'original_filename': att.original_filename,
                    'file_type': att.file_type,
                    'description': att.description,
                    'uploaded_at': att.uploaded_at.isoformat() if att.uploaded_at else None
                }
                segment_data['attachments'].append(attachment_data)
            session_export_data['segments'].append(segment_data)

        response = jsonify(session_export_data)
        response.headers['Content-Disposition'] = f"attachment; filename=session_{session.id}_export.json"
        return response
        
    except Exception as e:
        logger.error(f"Error exporting session {session_id} to JSON: {str(e)}")
        return jsonify({'error': str(e)}), 500
