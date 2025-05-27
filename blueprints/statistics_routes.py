import logging
from flask import Blueprint, jsonify
from datetime import datetime, timedelta
from sqlalchemy import func

from models import db, Session, Segment, Tag, Attachment, session_tags, segment_tags

# Initialize logger
logger = logging.getLogger(__name__)

statistics_bp = Blueprint('statistics_api', __name__)

# API Routes
@statistics_bp.route('/api/statistics/overview', methods=['GET'])
def get_statistics_overview():
    """獲取系統統計概覽"""
    try:
        # 基本統計
        total_sessions = Session.query.count()
        total_segments = Segment.query.count()
        total_tags = Tag.query.count()
        total_attachments = Attachment.query.count()
        
        # 最近30天的活動
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_sessions = Session.query.filter(Session.created_at >= thirty_days_ago).count()
        recent_segments = Segment.query.filter(Segment.created_at >= thirty_days_ago).count()
        
        # 標籤分類統計
        tag_categories = db.session.query(Tag.category, func.count(Tag.id).label('count'))\
            .group_by(Tag.category)\
            .all()
        
        # 段落類型統計
        segment_types = db.session.query(Segment.segment_type, func.count(Segment.id).label('count'))\
            .group_by(Segment.segment_type)\
            .all()
        
        # 活躍度分析 - 按月統計
        monthly_activity = db.session.query(
            func.strftime('%Y-%m', Session.created_at).label('month'),
            func.count(Session.id).label('count')
        ).filter(Session.created_at >= datetime.utcnow() - timedelta(days=365))\
         .group_by(func.strftime('%Y-%m', Session.created_at))\
         .order_by(func.strftime('%Y-%m', Session.created_at).asc())\
         .all() # Ensure consistent ordering for timeline
        
        return jsonify({
            'basic_stats': {
                'total_sessions': total_sessions,
                'total_segments': total_segments,
                'total_tags': total_tags,
                'total_attachments': total_attachments,
                'recent_sessions': recent_sessions,
                'recent_segments': recent_segments
            },
            'tag_categories': [{'category': cat, 'count': count} for cat, count in tag_categories],
            'segment_types': [{'type': stype, 'count': count} for stype, count in segment_types],
            'monthly_activity': [{'month': month, 'count': count} for month, count in monthly_activity]
        })
        
    except Exception as e:
        logger.error(f"Error getting statistics overview: {str(e)}")
        return jsonify({'error': str(e)}), 500

@statistics_bp.route('/api/statistics/tags', methods=['GET'])
def get_tag_statistics():
    """獲取標籤使用統計"""
    try:
        # 最常用的標籤
        popular_tags = db.session.query(
            Tag.name,
            Tag.category,
            Tag.color,
            func.count(segment_tags.c.tag_id).label('usage_count')
        ).outerjoin(segment_tags, Tag.id == segment_tags.c.tag_id)\
         .group_by(Tag.id)\
         .order_by(func.count(segment_tags.c.tag_id).desc())\
         .limit(20)\
         .all()
        
        return jsonify({
            'popular_tags': [{
                'name': name,
                'category': category,
                'color': color,
                'usage_count': usage_count
            } for name, category, color, usage_count in popular_tags]
        })
        
    except Exception as e:
        logger.error(f"Error getting tag statistics: {str(e)}")
        return jsonify({'error': str(e)}), 500

@statistics_bp.route('/api/statistics/learning-progress', methods=['GET'])
def get_learning_progress():
    """獲取學習進度分析"""
    try:
        # 按領域統計學習內容
        domain_progress = db.session.query(
            Tag.name.label('domain'),
            func.count(Session.id).label('session_count'),
            func.count(Segment.id).label('segment_count')
        ).join(session_tags, Tag.id == session_tags.c.tag_id)\
         .join(Session, session_tags.c.session_id == Session.id)\
         .outerjoin(Segment, Session.id == Segment.session_id)\
         .filter(Tag.category == '領域')\
         .group_by(Tag.name)\
         .all()
        
        # 學習時間線
        timeline = db.session.query(
            func.date(Session.created_at).label('date'), # Use func.date for proper grouping
            func.count(Session.id).label('sessions'),
            func.count(Segment.id).label('segments') # This will count segments across all sessions for that date
        ).outerjoin(Segment, Session.id == Segment.session_id)\
         .filter(Session.created_at >= datetime.utcnow() - timedelta(days=90))\
         .group_by(func.date(Session.created_at))\
         .order_by(func.date(Session.created_at).asc())\
         .all() # Ensure consistent ordering
        
        return jsonify({
            'domain_progress': [{
                'domain': domain,
                'session_count': session_count,
                'segment_count': segment_count
            } for domain, session_count, segment_count in domain_progress],
            'timeline': [{
                'date': str(date_val), # Ensure date is stringified
                'sessions': sessions,
                'segments': segments
            } for date_val, sessions, segments in timeline] # Renamed date to date_val to avoid conflict
        })
        
    except Exception as e:
        logger.error(f"Error getting learning progress: {str(e)}")
        return jsonify({'error': str(e)}), 500
