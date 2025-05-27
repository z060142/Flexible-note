from flask import Blueprint, render_template, request, jsonify, redirect, url_for, send_from_directory
from datetime import datetime
from models import db, Session, Segment, Tag, Attachment
from config import CATEGORY_COLORS

main_bp = Blueprint('main', __name__)

# 首頁 - 顯示所有課程
@main_bp.route('/')
def index():
    sessions = Session.query.order_by(Session.date.desc()).all()
    return render_template('index.html', sessions=sessions)

# 課程詳情頁
@main_bp.route('/session/<int:session_id>')
def session_detail(session_id):
    session = Session.query.get_or_404(session_id)
    segments = session.segments.order_by(Segment.order_index).all()
    return render_template('session_detail.html', session=session, segments=segments, category_colors=CATEGORY_COLORS)

# 語義搜尋頁面
@main_bp.route('/semantic-search')
def semantic_search_page():
    """語義搜尋頁面"""
    return render_template('semantic_search.html')

# Tag Management Page
@main_bp.route('/tags/manage')
def manage_tags():
    tags = Tag.query.order_by(Tag.category, Tag.name).all()
    return render_template('tag_management.html', tags=tags, category_colors=CATEGORY_COLORS)

# 統計分析和批量操作頁面路由
@main_bp.route('/statistics')
def statistics_dashboard():
    """統計分析頁面"""
    return render_template('statistics.html')

@main_bp.route('/batch-operations')
def batch_operations_page():
    """批量操作頁面"""
    return render_template('batch_operations.html')

# LLM 課程錄入功能
@main_bp.route('/llm-course-create')
def llm_course_create():
    """LLM 課程錄入頁面"""
    return render_template('llm_course_create.html', datetime=datetime)

# 測試上傳頁面 (僅在開發模式下)
@main_bp.route('/test-upload')
def test_upload():
    return render_template('test_upload.html')
