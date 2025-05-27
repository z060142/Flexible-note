import os
import logging
from flask import Blueprint, request, jsonify, current_app

from models import db, Segment, Session, Tag, Attachment
from config import CATEGORY_COLORS

# Initialize logger
logger = logging.getLogger(__name__)

# Create Blueprint
batch_bp = Blueprint('batch_api', __name__)

# API Routes
@batch_bp.route('/api/batch/tags/add', methods=['POST'])
def batch_add_tags():
    """批量添加標籤到多個段落"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        segment_ids = data.get('segment_ids', [])
        tags_data = data.get('tags', [])
        
        if not segment_ids or not tags_data:
            return jsonify({'success': False, 'error': 'Missing segment_ids or tags'}), 400
        
        # 驗證段落存在
        segments = Segment.query.filter(Segment.id.in_(segment_ids)).all()
        if len(segments) != len(set(segment_ids)): # Check if all provided ids were found
            logger.warning(f"Batch add tags: Some segments not found. Provided: {segment_ids}, Found: {[s.id for s in segments]}")
            # Decide if this is a hard error or if we proceed with found segments
            # For now, let's consider it a partial success if some are found, but log it.
            if not segments:
                 return jsonify({'success': False, 'error': 'No valid segments found'}), 404


        # 處理標籤
        processed_tags = []
        for tag_data_item in tags_data: # Renamed to avoid conflict
            tag_name = None
            tag_category = '其他' # Default category
            tag_color = CATEGORY_COLORS.get(tag_category, '#6c757d') # Default color

            if isinstance(tag_data_item, dict):
                tag_name = tag_data_item.get('name')
                tag_category = tag_data_item.get('category', tag_category)
                # Ensure color is fetched based on the actual category
                tag_color = tag_data_item.get('color', CATEGORY_COLORS.get(tag_category, tag_color))
            else:
                tag_name = str(tag_data_item)
                # Color will be the default for '其他' or the one from CATEGORY_COLORS if '其他' is defined there
                tag_color = CATEGORY_COLORS.get(tag_category, '#6c757d')


            if tag_name and tag_name.strip():
                tag_name = tag_name.strip()
                tag = Tag.query.filter_by(name=tag_name, category=tag_category).first()
                if not tag:
                    tag = Tag(
                        name=tag_name,
                        category=tag_category,
                        color=tag_color
                    )
                    db.session.add(tag)
                    db.session.flush() # Ensure tag has ID before appending
                processed_tags.append(tag)
        
        # 批量添加標籤到段落
        added_count = 0
        for segment in segments: # Iterate over the segments that were actually found
            for tag_item in processed_tags: # Renamed
                if tag_item not in segment.tags:
                    segment.tags.append(tag_item)
                    added_count += 1
        
        if added_count > 0 or not tags_data : # Commit if any changes were made or if no tags were to be added (vacuously true)
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'成功為 {len(segments)} 個段落添加了 {len(processed_tags)} 個標籤。 {added_count} 個新關聯已創建。',
            'added_relations': added_count,
            'processed_segments': [s.id for s in segments]
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in batch_add_tags: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@batch_bp.route('/api/batch/segments/delete', methods=['POST'])
def batch_delete_segments():
    """批量刪除段落"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        segment_ids = data.get('segment_ids', [])
        
        if not segment_ids:
            return jsonify({'success': False, 'error': 'No segment_ids provided'}), 400
        
        # 獲取要刪除的段落
        segments = Segment.query.filter(Segment.id.in_(segment_ids)).all()
        
        if not segments: # No segments found for the given IDs
            return jsonify({'success': False, 'error': 'No segments found for the provided IDs'}), 404
        
        deleted_count = 0
        for segment in segments:
            # 刪除相關附件文件
            for attachment in segment.attachments:
                try:
                    # Ensure UPLOAD_FOLDER is correctly accessed via current_app
                    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], attachment.filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Deleted attachment file: {file_path}")
                except Exception as e:
                    logger.error(f"Error deleting file {attachment.filename}: {str(e)}")
                db.session.delete(attachment)
            
            db.session.delete(segment)
            deleted_count += 1
        
        if deleted_count > 0:
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'成功刪除了 {deleted_count} 個段落',
            'deleted_count': deleted_count,
            'attempted_to_delete_ids': segment_ids
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in batch_delete_segments: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@batch_bp.route('/api/segments', methods=['GET'])
def get_all_segments():
    """獲取所有段落（用於批量操作）"""
    try:
        segments_query = db.session.query(
            Segment.id,
            Segment.title,
            Segment.content,
            Segment.segment_type,
            Segment.session_id,
            Session.title.label('session_title')
        ).join(Session, Segment.session_id == Session.id)\
         .order_by(Session.date.desc(), Segment.order_index)\
         .all()
        
        segment_list = []
        for segment in segments_query:
            segment_list.append({
                'id': segment.id,
                'title': segment.title or f'段落 {segment.id}',
                'content_preview': segment.content[:100] if segment.content else '', # Renamed for clarity
                'segment_type': segment.segment_type,
                'session_id': segment.session_id,
                'session_title': segment.session_title
            })
        
        return jsonify(segment_list)
        
    except Exception as e:
        logger.error(f"Error in get_all_segments: {str(e)}")
        return jsonify({'error': str(e)}), 500

@batch_bp.route('/api/sessions', methods=['GET'])
def get_all_sessions():
    """獲取所有課程（用於批量操作）"""
    try:
        sessions_query = Session.query.order_by(Session.date.desc()).all() # Renamed variable
        
        session_list = []
        for session_item in sessions_query: # Renamed variable
            session_list.append({
                'id': session_item.id,
                'title': session_item.title,
                'overview_preview': session_item.overview[:100] if session_item.overview else '', # Renamed and added preview
                'date': session_item.date.isoformat() if session_item.date else None,
                'segment_count': len(session_item.segments), # Use len() for direct relationship
                'tag_count': len(session_item.tags)  # Use len() for direct relationship
            })
        
        return jsonify(session_list)
        
    except Exception as e:
        logger.error(f"Error in get_all_sessions: {str(e)}")
        return jsonify({'error': str(e)}), 500
