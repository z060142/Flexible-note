import logging # Import logging
from flask import Blueprint, request, jsonify
from sqlalchemy import func

from models import db, Tag, segment_tags, Session # Added Session for potential future use if needed, and to match app.py
from config import CATEGORY_COLORS # Import CATEGORY_COLORS

tag_bp = Blueprint('tag', __name__)
logger = logging.getLogger(__name__) # Initialize logger

# API Routes
@tag_bp.route('/api/tags', methods=['GET'])
def get_tags():
    try:
        category = request.args.get('category')
        query = Tag.query
        if category: 
            query = query.filter_by(category=category)
        tags = query.all()
        return jsonify([tag.to_dict() for tag in tags])
    except Exception as e:
        logger.error(f"Error getting tags: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tag_bp.route('/api/tags/search', methods=['GET'])
def search_tags():
    try:
        q = request.args.get('q', '')
        context = request.args.get('context', '')  # 查詢上下文：symptom_to_cause, cause_to_treatment等
        category_filter = request.args.get('category', '')  # 分類過濾
        
        if not q:
            return jsonify([])
        
        # 構建基礎查詢
        query = Tag.query.filter(Tag.name.contains(q))
        
        # 根據上下文智能過濾分類
        if context == 'symptom_to_cause':
            # 症狀診斷：優先顯示症狀、位置相關標籤
            preferred_categories = ['症狀', '位置', '施術位置', '治療位置']
            query = query.filter(Tag.category.in_(preferred_categories))
        elif context == 'cause_to_treatment':
            # 治療方案：優先顯示病因、治療相關標籤
            preferred_categories = ['病因', '手法', '治療', '領域']
            query = query.filter(Tag.category.in_(preferred_categories))
        elif context == 'method_analysis':
            # 手法分析：優先顯示手法相關標籤
            preferred_categories = ['手法', '治療']
            query = query.filter(Tag.category.in_(preferred_categories))
        elif category_filter:
            # 如果指定了分類過濾
            query = query.filter(Tag.category == category_filter)
        
        # 執行查詢，按使用頻率排序
        tags = query.outerjoin(segment_tags, Tag.id == segment_tags.c.tag_id)\
                   .group_by(Tag.id)\
                   .order_by(func.count(segment_tags.c.tag_id).desc(), Tag.name)\
                   .limit(15)\
                   .all()
        
        # 如果上下文查詢結果太少，補充其他相關標籤
        if len(tags) < 5 and context:
            additional_query = Tag.query.filter(Tag.name.contains(q))
            if context == 'symptom_to_cause':
                # 補充病因標籤（因為症狀可能對應病因）
                additional_query = additional_query.filter(Tag.category == '病因')
            elif context == 'cause_to_treatment':
                # 補充症狀標籤（幫助更好理解病因）
                additional_query = additional_query.filter(Tag.category == '症狀')
            
            additional_tags = additional_query.limit(5).all()
            # 避免重複
            existing_ids = {tag.id for tag in tags}
            tags.extend([tag for tag in additional_tags if tag.id not in existing_ids])
        
        return jsonify([tag.to_dict() for tag in tags])
    except Exception as e:
        logger.error(f"Error searching tags: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tag_bp.route('/api/tag/<int:tag_id>/update', methods=['POST'])
def update_tag(tag_id):
    try:
        tag = Tag.query.get(tag_id)
        if not tag: 
            return jsonify({'error': 'Tag not found'}), 404
            
        data = request.get_json()
        if not data: 
            return jsonify({'error': 'No input data provided'}), 400

        new_name = data.get('name', tag.name).strip()
        new_category = data.get('category', tag.category).strip()
        
        if new_name != tag.name or new_category != tag.category: 
            existing_tag = Tag.query.filter(
                Tag.name == new_name, 
                Tag.category == new_category,
                Tag.id != tag_id
            ).first()
            if existing_tag: 
                return jsonify({
                    'error': f"Tag name '{new_name}' already exists in category '{new_category}'."
                }), 400

        tag.name = new_name
        tag.category = new_category
        # Update color using CATEGORY_COLORS if provided, else keep existing or default
        tag.color = data.get('color', CATEGORY_COLORS.get(new_category, tag.color if tag.color else '#6c757d'))
        tag.description = data.get('description', tag.description)
        
        db.session.commit()
        return jsonify({'success': True, 'tag': tag.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating tag {tag_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tag_bp.route('/api/tag/<int:tag_id>/delete', methods=['DELETE'])
def delete_tag(tag_id):
    try:
        tag = Tag.query.get(tag_id)
        if not tag: 
            return jsonify({'error': 'Tag not found'}), 404
            
        db.session.delete(tag)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Tag deleted'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting tag {tag_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500
