import os
import logging
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import json
from sqlalchemy import func, and_, or_, text

# 添加這個重要的導入
from models import db, Session, Segment, Tag, Attachment, QueryRelation, session_tags, segment_tags

# 添加缺失的導入
from collections import Counter

# 配置日誌
logger = logging.getLogger(__name__)

# 導入向量搜尋服務
try:
    from vector_service import get_chroma_manager, get_hybrid_search_engine, initialize_vector_db
    VECTOR_SEARCH_ENABLED = True
except ImportError as e:
    print(f"向量搜尋服務導入失敗: {e}")
    print("將使用傳統搜尋功能，請安裝必要的依賴：chromadb, sentence-transformers")
    VECTOR_SEARCH_ENABLED = False

# Default colors for tag categories (can be expanded)
CATEGORY_COLORS = {
    '手法': '#007bff',    # Blue
    '症狀': '#dc3545',    # Red
    '位置': '#28a745',    # Green
    '施術位置': '#17a2b8', # Teal
    '治療位置': '#ffc107', # Yellow
    '領域': '#6610f2',    # Indigo
    '病因': '#fd7e14',    # Orange
    '內容': '#6c757d',    # Grey (For default segment type, or tag category)
    '理論': '#ffc107',    # Yellow 
    '案例': '#20c997',    # Cyan
    '其他': '#6c757d'     # Grey
}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///knowledge.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'pdf', 'doc', 'docx'}

db.init_app(app)
migrate = Migrate(app, db)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_upload_folder():
    """確保上傳資料夾存在"""
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)
        print(f"創建上傳資料夾: {upload_folder}")

# 首頁 - 顯示所有課程
@app.route('/')
def index():
    sessions = Session.query.order_by(Session.date.desc()).all()
    return render_template('index.html', sessions=sessions)

# 課程詳情頁
@app.route('/session/<int:session_id>')
def session_detail(session_id):
    session = Session.query.get_or_404(session_id)
    segments = session.segments.order_by(Segment.order_index).all()
    return render_template('session_detail.html', session=session, segments=segments, category_colors=CATEGORY_COLORS)

# 語義搜尋頁面
@app.route('/semantic-search')
def semantic_search_page():
    """語義搜尋頁面"""
    return render_template('semantic_search.html')

# 新增課程
@app.route('/session/new', methods=['GET', 'POST'])
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
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return render_template('session_form.html', datetime=datetime)

# 編輯課程
@app.route('/session/<int:session_id>/edit', methods=['GET', 'POST'])
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
            return jsonify({'success': False, 'error': str(e)}), 500
        
    all_tags = Tag.query.all()
    return render_template('session_edit_form.html', session=session, all_tags=all_tags)

# 刪除課程
@app.route('/session/<int:session_id>/delete', methods=['POST'])
def delete_session(session_id):
    session = Session.query.get_or_404(session_id)
    try:
        # Delete associated segments and their attachments
        for segment in session.segments:
            for attachment in segment.attachments:
                # Delete physical file
                try:
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], attachment.filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    # Log error or handle, but continue deletion process
                    print(f"Error deleting file {attachment.filename}: {str(e)}")
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
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting session {session_id}: {str(e)}")
        return redirect(url_for('session_detail', session_id=session_id))

# 新增段落
@app.route('/session/<int:session_id>/segment', methods=['POST'])
def add_segment(session_id):
    session = Session.query.get_or_404(session_id)
    
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
        return jsonify({'success': False, 'error': str(e)}), 500

# 上傳附件
@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if file and allowed_file(file.filename):
            original_filename = file.filename
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(original_filename)}"
            upload_folder_path = app.config['UPLOAD_FOLDER']
            
            ensure_upload_folder()
            file_path_on_disk = os.path.join(upload_folder_path, filename)
            file.save(file_path_on_disk)
            
            ext = filename.rsplit('.', 1)[1].lower()
            file_type = 'document' 
            if ext in ['png', 'jpg', 'jpeg', 'gif']: 
                file_type = 'image'
            elif ext in ['mp4', 'avi']: 
                file_type = 'video'
            
            attachment = Attachment(
                filename=filename, 
                original_filename=original_filename, 
                file_type=file_type,
                file_path=filename, 
                description=request.form.get('description', '')
            )
            db.session.add(attachment)
            
            segment_id = request.form.get('segment_id', type=int)
            processed_segment_id = None 
            if segment_id is not None: 
                segment = Segment.query.get(segment_id)
                if segment:
                    segment.attachments.append(attachment)
                    processed_segment_id = segment.id
                    
            db.session.commit() 
            
            response_data = {
                'success': True, 
                'attachment_id': attachment.id, 
                'filename': attachment.original_filename,
                'file_path': filename,
                'file_type': file_type
            }
            if processed_segment_id is not None: 
                response_data['segment_id'] = processed_segment_id
                
            return jsonify(response_data)
        else:
            return jsonify({'error': 'File type not allowed'}), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Route to serve uploaded files directly
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# 添加别名路由以兼容模板中的引用
@app.route('/serve_uploads/<path:filename>')
def serve_uploads(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Route to serve files based on Attachment records
@app.route('/attachment/<int:attachment_id>')
def serve_attachment(attachment_id):
    attachment = Attachment.query.get(attachment_id)
    if not attachment: 
        return "Attachment not found", 404
    return send_from_directory(app.config['UPLOAD_FOLDER'], attachment.filename, as_attachment=False)

# Tag Management Page
@app.route('/tags/manage')
def manage_tags():
    tags = Tag.query.order_by(Tag.category, Tag.name).all()
    return render_template('tag_management.html', tags=tags, category_colors=CATEGORY_COLORS)

# API Routes
@app.route('/api/tags', methods=['GET'])
def get_tags():
    try:
        category = request.args.get('category')
        query = Tag.query
        if category: 
            query = query.filter_by(category=category)
        tags = query.all()
        return jsonify([tag.to_dict() for tag in tags])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tags/search', methods=['GET'])
def search_tags():
    try:
        q = request.args.get('q', '')
        if not q:
            return jsonify([])
            
        tags = Tag.query.filter(Tag.name.contains(q)).limit(10).all()
        return jsonify([tag.to_dict() for tag in tags])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tag/<int:tag_id>/update', methods=['POST'])
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
        tag.color = data.get('color', tag.color)
        tag.description = data.get('description', tag.description)
        
        db.session.commit()
        return jsonify({'success': True, 'tag': tag.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tag/<int:tag_id>/delete', methods=['DELETE'])
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
        return jsonify({'error': str(e)}), 500

@app.route('/api/segment/<int:segment_id>', methods=['GET'])
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
        return jsonify({'error': str(e)}), 500

@app.route('/api/segment/<int:segment_id>/update', methods=['POST']) 
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
        return jsonify({'error': str(e)}), 500

@app.route('/api/segment/<int:segment_id>/delete', methods=['DELETE'])
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
        return jsonify({'error': str(e)}), 500

@app.route('/api/session/<int:session_id>/export', methods=['GET'])
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
        return jsonify({'error': str(e)}), 500

# 向量數據庫狀態 API
@app.route('/api/vector/status')
def vector_status():
    """向量數據庫狀態檢查"""
    if not VECTOR_SEARCH_ENABLED:
        return jsonify({'enabled': False, 'message': 'Vector search dependencies not installed'})
    
    try:
        chroma_manager = get_chroma_manager()
        stats = chroma_manager.get_collection_stats()
        return jsonify({
            'enabled': True,
            'status': 'healthy',
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'enabled': True,
            'status': 'error',
            'error': str(e)
        })

# 數據同步 API
@app.route('/api/vector/sync', methods=['POST'])
def sync_vector_db():
    """同步數據到向量數據庫"""
    if not VECTOR_SEARCH_ENABLED:
        return jsonify({'success': False, 'error': 'Vector search not enabled'}), 503
    
    try:
        from vector_service import sync_existing_data
        sync_existing_data()
        return jsonify({'success': True, 'message': '數據同步完成'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# 新增語義搜尋API端點
@app.route('/api/search/semantic', methods=['POST'])
def semantic_search():
    """語義搜尋 API"""
    if not VECTOR_SEARCH_ENABLED:
        return jsonify({'error': 'Vector search is not enabled. Please install required dependencies.'}), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'results': [], 'message': 'No search data provided'})
        
        query = data.get('query', '')
        search_type = data.get('search_type', 'hybrid')  # semantic, keyword, hybrid
        limit = data.get('limit', 10)
        content_type = data.get('content_type')  # session, segment, or None for all
        
        if not query.strip():
            return jsonify({'results': [], 'message': 'Please provide a search query'})
        
        # 使用混合搜尋引擎
        search_engine = get_hybrid_search_engine()
        results = search_engine.search(query, search_type, limit)
        
        # 轉換結果格式以符合前端預期
        formatted_results = []
        for result in results:
            formatted_result = {
                'search_type': result['type'],
                'score': result['score'],
                'content_type': result['content_type'],
                'title': result['title'],
                'content_preview': result['content'][:200] + '...' if len(result['content']) > 200 else result['content'],
                'metadata': result['metadata']
            }
            
            # 根據內容類型添加特定字段
            if result['content_type'] == 'session':
                formatted_result['session_id'] = result['metadata'].get('session_id')
                formatted_result['session_title'] = result['title']
            elif result['content_type'] == 'segment':
                formatted_result['segment_id'] = result['metadata'].get('segment_id')
                formatted_result['session_id'] = result['metadata'].get('session_id')
                formatted_result['session_title'] = result['metadata'].get('session_title', '')
                formatted_result['segment_title'] = result['title']
            
            formatted_results.append(formatted_result)
        
        return jsonify({
            'results': formatted_results,
            'query': query,
            'search_type': search_type,
            'total_count': len(formatted_results)
        })
        
    except Exception as e:
        logger.error(f"語義搜尋失敗: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search/suggestions', methods=['GET'])
def search_suggestions():
    """搜尋建議 API"""
    try:
        query = request.args.get('q', '').strip()
        if len(query) < 2:
            return jsonify([])
        
        # 基於標籤名稱的建議
        tag_suggestions = Tag.query.filter(
            Tag.name.contains(query)
        ).limit(5).all()
        
        suggestions = []
        for tag in tag_suggestions:
            suggestions.append({
                'text': tag.name,
                'type': 'tag',
                'category': tag.category,
                'color': tag.color
            })
        
        # 基於課程標題的建議
        session_suggestions = Session.query.filter(
            Session.title.contains(query)
        ).limit(3).all()
        
        for session in session_suggestions:
            suggestions.append({
                'text': session.title,
                'type': 'session',
                'id': session.id
            })
        
        return jsonify(suggestions)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({'results': [], 'message': 'No search data provided'})
                
            query_type = data.get('query_type', 'symptom_to_cause')
            results = []
            
            if query_type == 'symptom_to_cause':
                symptom_tag_names = data.get('symptom_tags', [])
                location_name = data.get('location', None)
                
                if not symptom_tag_names: 
                    return jsonify({'results': [], 'message': 'Please provide at least one symptom tag.'})
                    
                query = db.session.query(Segment).distinct().join(Segment.tags).filter(
                    Tag.category == '症狀', 
                    Tag.name.in_(symptom_tag_names)
                )
                
                if location_name: 
                    query = query.filter(
                        Segment.tags.any(and_(Tag.category == '位置', Tag.name.contains(location_name)))
                    )
                    
                found_segments = query.all()
                
                for segment in found_segments:
                    potential_cause_tags, matched_symptoms_on_segment = [], []
                    for tag in segment.tags:
                        if tag.category == '病因': 
                            potential_cause_tags.append(tag.to_dict())
                        if tag.name in symptom_tag_names and tag.category == '症狀': 
                            matched_symptoms_on_segment.append(tag.to_dict())
                            
                    if segment.session:
                        for tag in segment.session.tags:
                            if tag.category == '病因' and not any(pct['id'] == tag.id for pct in potential_cause_tags):
                                potential_cause_tags.append(tag.to_dict())
                                
                    if potential_cause_tags: 
                        results.append({
                            "segment_id": segment.id, 
                            "segment_title": segment.title,
                            "segment_content_preview": (segment.content[:100] + "...") if segment.content else "",
                            "session_id": segment.session_id, 
                            "session_title": segment.session.title if segment.session else "N/A",
                            "potential_cause_tags": potential_cause_tags, 
                            "matched_symptoms": matched_symptoms_on_segment
                        })
                
            elif query_type == 'cause_to_treatment':
                cause_tag_names = data.get('cause_tags', [])
                preferred_domain_name = data.get('preferred_domain', None)
                
                if not cause_tag_names: 
                    return jsonify({'results': [], 'message': 'Please provide at least one cause tag.'})
                    
                query = db.session.query(Segment).distinct().join(Segment.tags).filter(
                    Tag.category == '病因', 
                    Tag.name.in_(cause_tag_names)
                )
                
                if preferred_domain_name:
                    query = query.join(Session, Segment.session_id == Session.id)\
                                 .filter(Session.tags.any(and_(Tag.category == '領域', Tag.name == preferred_domain_name)))
                                 
                found_segments = query.all()
                
                for segment in found_segments:
                    potential_treatment_tags, matched_causes_on_segment = [], []
                    for tag in segment.tags:
                        if tag.category in ['治療', '手法']: 
                            potential_treatment_tags.append(tag.to_dict())
                        if tag.name in cause_tag_names and tag.category == '病因': 
                            matched_causes_on_segment.append(tag.to_dict())
                            
                    if potential_treatment_tags or segment.segment_type == '治療':
                        results.append({
                            "segment_id": segment.id, 
                            "segment_title": segment.title,
                            "segment_content_preview": (segment.content[:100] + "...") if segment.content else "",
                            "segment_type": segment.segment_type, 
                            "session_id": segment.session_id,
                            "session_title": segment.session.title if segment.session else "N/A",
                            "potential_treatment_tags": potential_treatment_tags, 
                            "matched_causes": matched_causes_on_segment
                        })
            
            elif query_type == 'method_analysis':
                method_name = data.get('method_name', None)
                if not method_name: 
                    return jsonify({'results': [], 'message': 'Please provide a method name.'})
                    
                method_tag = Tag.query.filter_by(name=method_name, category='手法').first()
                if not method_tag: 
                    return jsonify({'results': [], 'message': f"Method tag '{method_name}' not found."})
                    
                segments_using_method = Segment.query.join(Segment.tags).filter(Tag.id == method_tag.id).all()
                unique_symptom_tags, unique_cause_tags, unique_cooccurring_methods, unique_location_tags = {}, {}, {}, {}
                
                for seg in segments_using_method:
                    for tag in seg.tags:
                        if tag.category == '症狀': 
                            unique_symptom_tags[tag.id] = tag
                        elif tag.category == '病因': 
                            unique_cause_tags[tag.id] = tag
                        elif tag.category == '手法' and tag.id != method_tag.id: 
                            unique_cooccurring_methods[tag.id] = tag
                        elif tag.category == '位置': 
                            unique_location_tags[tag.id] = tag
                            
                results.append({
                    "method_name": method_tag.name, 
                    "method_id": method_tag.id, 
                    "description": method_tag.description,
                    "applicable_symptoms": [t.to_dict() for t in unique_symptom_tags.values()],
                    "treated_causes": [t.to_dict() for t in unique_cause_tags.values()],
                    "common_locations": [t.to_dict() for t in unique_location_tags.values()],
                    "related_methods": [t.to_dict() for t in unique_cooccurring_methods.values()],
                    "example_segments": [{
                        "segment_id": s.id, 
                        "segment_title": s.title, 
                        "session_id": s.session_id, 
                        "session_title": s.session.title if s.session else "N/A"
                    } for s in segments_using_method[:5]]
                })
            
            elif query_type == 'relation_map':
                start_point = data.get('start_point', None)
                depth = data.get('depth', 2)
                
                if not start_point:
                    return jsonify({'results': [], 'message': 'Please provide a start point.'})
                
                # 構建關聯圖數據
                graph_data = build_relation_graph(start_point, depth)
                return jsonify(graph_data)

            return jsonify({'results': results})
            
        except Exception as e:
            return jsonify({'results': [], 'error': str(e)}), 500
    
    return render_template('search.html')

@app.route('/api/relation', methods=['POST'])
def create_relation():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        relation = QueryRelation(
            relation_type=data.get('relation_type'),
            source_type=data.get('source_type'),
            source_id=data.get('source_id'),
            target_type=data.get('target_type'),
            target_id=data.get('target_id'),
            strength=data.get('strength', 1.0),
            notes=data.get('notes', '')
        )
        db.session.add(relation)
        db.session.commit()
        return jsonify({'success': True, 'relation_id': relation.id})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# 統計分析API端點
@app.route('/api/statistics/overview')
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
        tag_categories = db.session.query(Tag.category, func.count(Tag.id))\
            .group_by(Tag.category)\
            .all()
        
        # 段落類型統計
        segment_types = db.session.query(Segment.segment_type, func.count(Segment.id))\
            .group_by(Segment.segment_type)\
            .all()
        
        # 活躍度分析 - 按月統計
        monthly_activity = db.session.query(
            func.strftime('%Y-%m', Session.created_at).label('month'),
            func.count(Session.id).label('count')
        ).filter(Session.created_at >= datetime.utcnow() - timedelta(days=365))\
         .group_by(func.strftime('%Y-%m', Session.created_at))\
         .order_by('month')\
         .all()
        
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
        return jsonify({'error': str(e)}), 500

@app.route('/api/statistics/tags')
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
        return jsonify({'error': str(e)}), 500

@app.route('/api/statistics/learning-progress')
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
            func.date(Session.created_at).label('date'),
            func.count(Session.id).label('sessions'),
            func.count(Segment.id).label('segments')
        ).outerjoin(Segment, Session.id == Segment.session_id)\
         .filter(Session.created_at >= datetime.utcnow() - timedelta(days=90))\
         .group_by(func.date(Session.created_at))\
         .order_by('date')\
         .all()
        
        return jsonify({
            'domain_progress': [{
                'domain': domain,
                'session_count': session_count,
                'segment_count': segment_count
            } for domain, session_count, segment_count in domain_progress],
            'timeline': [{
                'date': str(date),
                'sessions': sessions,
                'segments': segments
            } for date, sessions, segments in timeline]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 批量操作API端點
@app.route('/api/batch/tags/add', methods=['POST'])
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
        if len(segments) != len(segment_ids):
            return jsonify({'success': False, 'error': 'Some segments not found'}), 404
        
        # 處理標籤
        processed_tags = []
        for tag_data in tags_data:
            if isinstance(tag_data, dict):
                tag_name = tag_data.get('name')
                tag_category = tag_data.get('category', '其他')
                tag_color = tag_data.get('color', CATEGORY_COLORS.get(tag_category, '#6c757d'))
            else:
                tag_name = str(tag_data)
                tag_category = '其他'
                tag_color = '#6c757d'
            
            if tag_name:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(
                        name=tag_name,
                        category=tag_category,
                        color=tag_color
                    )
                    db.session.add(tag)
                    db.session.flush()
                processed_tags.append(tag)
        
        # 批量添加標籤到段落
        added_count = 0
        for segment in segments:
            for tag in processed_tags:
                if tag not in segment.tags:
                    segment.tags.append(tag)
                    added_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'成功為 {len(segments)} 個段落添加了 {len(processed_tags)} 個標籤',
            'added_relations': added_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/batch/segments/delete', methods=['POST'])
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
        
        if not segments:
            return jsonify({'success': False, 'error': 'No segments found'}), 404
        
        deleted_count = 0
        for segment in segments:
            # 刪除相關附件文件
            for attachment in segment.attachments:
                try:
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], attachment.filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting file {attachment.filename}: {str(e)}")
                db.session.delete(attachment)
            
            db.session.delete(segment)
            deleted_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'成功刪除了 {deleted_count} 個段落',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/segments')
def get_all_segments():
    """獲取所有段落（用於批量操作）"""
    try:
        segments = db.session.query(
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
        for segment in segments:
            segment_list.append({
                'id': segment.id,
                'title': segment.title or f'段落 {segment.id}',
                'content': segment.content[:100] if segment.content else '',
                'segment_type': segment.segment_type,
                'session_id': segment.session_id,
                'session_title': segment.session_title
            })
        
        return jsonify(segment_list)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions')
def get_all_sessions():
    """獲取所有課程（用於批量操作）"""
    try:
        sessions = Session.query.order_by(Session.date.desc()).all()
        
        session_list = []
        for session in sessions:
            session_list.append({
                'id': session.id,
                'title': session.title,
                'overview': session.overview,
                'date': session.date.isoformat() if session.date else None,
                'segment_count': session.segments.count(),
                'tag_count': len(session.tags)
            })
        
        return jsonify(session_list)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """系統健康檢查"""
    try:
        # 檢查資料庫連接
        db.session.execute(text('SELECT 1'))
        
        # 檢查上傳資料夾
        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            return jsonify({
                'status': 'warning',
                'message': 'Upload folder not found',
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        
        return jsonify({
            'status': 'healthy',
            'message': 'System is running normally',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected',
            'upload_folder': 'accessible'
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# 統計分析和批量操作頁面路由
@app.route('/statistics')
def statistics_dashboard():
    """統計分析頁面"""
    return render_template('statistics.html')

@app.route('/batch-operations')
def batch_operations_page():
    """批量操作頁面"""
    return render_template('batch_operations.html')

# 關聯圖譜構建函數
def build_relation_graph(start_point, depth=2):
    """構建關聯圖譜數據"""
    try:
        nodes = {}  # 存儲節點，避免重複
        links = []  # 存儲連接
        visited = set()  # 已處理的節點
        
        # 查找起始點
        start_tag = Tag.query.filter(
            or_(Tag.name.contains(start_point), Tag.name == start_point)
        ).first()
        
        if not start_tag:
            # 如果沒找到標籤，嘗試搜尋段落
            start_segments = Segment.query.filter(
                or_(Segment.title.contains(start_point), Segment.content.contains(start_point))
            ).limit(5).all()
            
            if not start_segments:
                return {
                    'nodes': [],
                    'links': [],
                    'message': f'找不到與 "{start_point}" 相關的內容'
                }
            
            # 從找到的段落中提取標籤作為起始點
            start_tags = []
            for segment in start_segments:
                start_tags.extend(segment.tags)
            
            if not start_tags:
                return {
                    'nodes': [],
                    'links': [],
                    'message': f'找到內容但沒有相關標籤'
                }
                
            start_tag = start_tags[0]  # 使用第一個標籤作為起始點
        
        # 構建圖譜
        def add_node(tag, node_type='tag', level=0):
            node_id = f"{node_type}_{tag.id}"
            if node_id not in nodes:
                nodes[node_id] = {
                    'id': node_id,
                    'name': tag.name,
                    'category': tag.category,
                    'color': tag.color or CATEGORY_COLORS.get(tag.category, '#6c757d'),
                    'type': node_type,
                    'level': level,
                    'size': 10 + level * 5  # 節點大小隨層級變化
                }
            return node_id
        
        def add_link(source_id, target_id, relation_type, strength=1.0):
            link_id = f"{source_id}_{target_id}"
            reverse_link_id = f"{target_id}_{source_id}"
            
            # 避免重複連接
            if not any(l['id'] == link_id or l['id'] == reverse_link_id for l in links):
                links.append({
                    'id': link_id,
                    'source': source_id,
                    'target': target_id,
                    'relation_type': relation_type,
                    'strength': strength,
                    'value': strength * 10  # 用於可視化中的連線粗細
                })
        
        def explore_relations(tag, current_depth, max_depth):
            if current_depth > max_depth or tag.id in visited:
                return
            
            visited.add(tag.id)
            current_node_id = add_node(tag, 'tag', current_depth)
            
            # 查找與此標籤共現的其他標籤
            related_tags = find_related_tags(tag)
            
            for related_tag, relation_info in related_tags.items():
                if related_tag.id != tag.id:
                    related_node_id = add_node(related_tag, 'tag', current_depth + 1)
                    add_link(
                        current_node_id, 
                        related_node_id, 
                        relation_info['type'],
                        relation_info['strength']
                    )
                    
                    # 遞迴探索下一層
                    if current_depth < max_depth:
                        explore_relations(related_tag, current_depth + 1, max_depth)
        
        def find_related_tags(tag):
            """找到與指定標籤相關的標籤"""
            related_tags = {}
            
            # 1. 在同一段落中共現的標籤
            segments_with_tag = Segment.query.join(Segment.tags).filter(Tag.id == tag.id).all()
            
            for segment in segments_with_tag:
                for other_tag in segment.tags:
                    if other_tag.id != tag.id:
                        if other_tag not in related_tags:
                            related_tags[other_tag] = {
                                'type': get_relation_type(tag, other_tag),
                                'strength': 0.1,
                                'co_occurrence': 0
                            }
                        related_tags[other_tag]['co_occurrence'] += 1
                        related_tags[other_tag]['strength'] += 0.1
            
            # 2. 在同一課程中的標籤
            sessions_with_tag = Session.query.join(Session.tags).filter(Tag.id == tag.id).all()
            
            for session in sessions_with_tag:
                for other_tag in session.tags:
                    if other_tag.id != tag.id:
                        if other_tag not in related_tags:
                            related_tags[other_tag] = {
                                'type': get_relation_type(tag, other_tag),
                                'strength': 0.05,
                                'co_occurrence': 0
                            }
                        related_tags[other_tag]['strength'] += 0.05
            
            # 3. 根據分類關係
            same_category_tags = Tag.query.filter(
                Tag.category == tag.category,
                Tag.id != tag.id
            ).limit(3).all()
            
            for other_tag in same_category_tags:
                if other_tag not in related_tags:
                    related_tags[other_tag] = {
                        'type': 'same_category',
                        'strength': 0.3,
                        'co_occurrence': 0
                    }
            
            # 4. 特定關係邏輯
            if tag.category == '症狀':
                # 症狀 -> 病因 -> 治療
                cause_tags = find_tags_by_pattern(tag, '病因')
                for cause_tag in cause_tags:
                    related_tags[cause_tag] = {
                        'type': 'symptom_to_cause',
                        'strength': 0.8,
                        'co_occurrence': 0
                    }
                    
            elif tag.category == '病因':
                # 病因 -> 治療方法
                treatment_tags = find_tags_by_pattern(tag, '手法')
                for treatment_tag in treatment_tags:
                    related_tags[treatment_tag] = {
                        'type': 'cause_to_treatment',
                        'strength': 0.7,
                        'co_occurrence': 0
                    }
            
            return related_tags
        
        def get_relation_type(tag1, tag2):
            """根據標籤分類確定關係類型"""
            if tag1.category == '症狀' and tag2.category == '病因':
                return 'symptom_to_cause'
            elif tag1.category == '病因' and tag2.category == '手法':
                return 'cause_to_treatment'
            elif tag1.category == '手法' and tag2.category == '位置':
                return 'method_to_location'
            elif tag1.category == tag2.category:
                return 'same_category'
            else:
                return 'co_occurrence'
        
        def find_tags_by_pattern(source_tag, target_category):
            """找到與源標籤在同一段落中出現的特定分類標籤"""
            segments = Segment.query.join(Segment.tags).filter(Tag.id == source_tag.id).all()
            found_tags = []
            
            for segment in segments:
                for tag in segment.tags:
                    if tag.category == target_category and tag not in found_tags:
                        found_tags.append(tag)
            
            return found_tags[:5]  # 限制數量
        
        # 開始構建圖譜
        explore_relations(start_tag, 0, depth)
        
        # 轉換為前端需要的格式
        nodes_list = list(nodes.values())
        
        # 計算節點的重要性（連接數）
        for node in nodes_list:
            connections = len([link for link in links if link['source'] == node['id'] or link['target'] == node['id']])
            node['importance'] = connections
            node['size'] = max(10, min(30, 10 + connections * 2))
        
        return {
            'nodes': nodes_list,
            'links': links,
            'center_node': f"tag_{start_tag.id}",
            'total_nodes': len(nodes_list),
            'total_links': len(links),
            'max_depth': depth
        }
        
    except Exception as e:
        logger.error(f"構建關聯圖失敗: {e}")
        return {
            'nodes': [],
            'links': [],
            'error': str(e)
        }

# 錯誤處理
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# 測試上傳頁面 (僅在開發模式下)
@app.route('/test-upload')
def test_upload():
    return render_template('test_upload.html')
