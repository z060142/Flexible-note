import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from datetime import datetime
import json
from sqlalchemy import func # Added line

from models import db, Session, Segment, Tag, Attachment, QueryRelation

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
    return render_template('session_detail.html', session=session, segments=segments)

# 新增課程
@app.route('/session/new', methods=['GET', 'POST'])
def new_session():
    if request.method == 'POST':
        data = request.get_json()
        
        session = Session(
            title=data['title'],
            overview=data.get('overview', ''),
            date=datetime.fromisoformat(data.get('date', datetime.now().isoformat()))
        )
        
        # 處理標籤
        tag_names = data.get('tags', [])
        for tag_name in tag_names:
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name, category=data.get('tag_category', '領域'))
            session.tags.append(tag)
        
        db.session.add(session)
        db.session.commit()
        
        return jsonify({'success': True, 'session_id': session.id})
    
    return render_template('session_form.html')

# 編輯課程
@app.route('/session/<int:session_id>/edit', methods=['GET', 'POST'])
def edit_session(session_id):
    session = Session.query.get_or_404(session_id)
    
    if request.method == 'POST':
        data = request.get_json()
        
        session.title = data.get('title', session.title)
        session.overview = data.get('overview', session.overview)
        
        if data.get('date'):
            session.date = datetime.fromisoformat(data.get('date'))
            
        # Update tags
        session.tags.clear() # Remove existing tags first
        tag_names = data.get('tags', [])
        tag_category = data.get('tag_category', '領域') # Default category
        
        for tag_name in tag_names:
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name, category=tag_category)
                db.session.add(tag) # Add new tag to session
            session.tags.append(tag)
            
        db.session.commit()
        return jsonify({'success': True, 'session_id': session.id})
        
    # GET request
    all_tags = Tag.query.all()
    return render_template('session_edit_form.html', session=session, all_tags=all_tags)

# 新增段落
@app.route('/session/<int:session_id>/segment', methods=['POST'])
def add_segment(session_id):
    session = Session.query.get_or_404(session_id)
    data = request.get_json()
    
    # 計算新段落的順序
    max_order = db.session.query(db.func.max(Segment.order_index)).filter_by(session_id=session_id).scalar() or 0
    
    segment = Segment(
        session_id=session_id,
        segment_type=data.get('segment_type', '內容'),
        title=data.get('title', ''),
        content=data.get('content', ''),
        order_index=max_order + 1
    )
    
    # 處理標籤
    tag_data = data.get('tags', [])
    for tag_info in tag_data:
        tag = Tag.query.filter_by(name=tag_info['name']).first()
        if not tag:
            tag = Tag(
                name=tag_info['name'],
                category=tag_info.get('category', '其他'),
                color=tag_info.get('color', '#808080')
            )
            db.session.add(tag)
        segment.tags.append(tag)
    
    db.session.add(segment)
    db.session.commit()
    
    return jsonify({'success': True, 'segment_id': segment.id})

# 上傳附件
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        original_filename = file.filename
        # Use a timestamp and secure_filename to create a unique and safe filename
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(original_filename)}"
        
        # Ensure upload folder exists
        upload_folder_path = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder_path, exist_ok=True)
        
        # Save the file
        file_path_on_disk = os.path.join(upload_folder_path, filename)
        file.save(file_path_on_disk)
        
        # Determine file type
        ext = filename.rsplit('.', 1)[1].lower()
        file_type = 'document' # Default
        if ext in ['png', 'jpg', 'jpeg', 'gif']:
            file_type = 'image'
        elif ext in ['mp4', 'avi']:
            file_type = 'video'
        
        # Create Attachment record
        attachment = Attachment(
            filename=filename, # Stored filename (unique and secure)
            original_filename=original_filename, # Original filename for display
            file_type=file_type,
            file_path=filename, # Path relative to UPLOAD_FOLDER, or just the filename
            description=request.form.get('description', '')
        )
        db.session.add(attachment)
        
        # Associate with segment if segment_id is provided
        segment_id = request.form.get('segment_id', type=int)
        processed_segment_id = None 
        if segment_id is not None: # Check if segment_id was provided and successfully typed to int
            segment = Segment.query.get(segment_id)
            if segment:
                segment.attachments.append(attachment)
                processed_segment_id = segment.id
            # else: if segment_id is provided but segment not found, we might log this
            # For now, the attachment is saved, but not associated if segment is invalid
                
        db.session.commit() # Saves attachment and any segment association
        
        response_data = {
            'success': True,
            'attachment_id': attachment.id,
            'filename': attachment.original_filename 
        }
        if processed_segment_id is not None:
            response_data['segment_id'] = processed_segment_id
            
        return jsonify(response_data)
    
    return jsonify({'error': 'File type not allowed'}), 400

# Route to serve uploaded files directly
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Route to serve files based on Attachment records
@app.route('/attachment/<int:attachment_id>')
def serve_attachment(attachment_id):
    attachment = Attachment.query.get(attachment_id)
    if not attachment:
        return "Attachment not found", 404
    
    return send_from_directory(app.config['UPLOAD_FOLDER'], attachment.filename, as_attachment=False)

# 標籤管理 API
@app.route('/api/tags', methods=['GET'])
def get_tags():
    category = request.args.get('category')
    query = Tag.query
    
    if category:
        query = query.filter_by(category=category)
    
    tags = query.all()
    return jsonify([tag.to_dict() for tag in tags])

@app.route('/api/tags/search', methods=['GET'])
def search_tags():
    q = request.args.get('q', '')
    tags = Tag.query.filter(Tag.name.contains(q)).limit(10).all()
    return jsonify([tag.to_dict() for tag in tags])

# Segment Detail API (GET)
@app.route('/api/segment/<int:segment_id>', methods=['GET'])
def get_segment_detail(segment_id):
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

# Segment Update API (POST/PUT)
@app.route('/api/segment/<int:segment_id>/update', methods=['POST']) 
def update_segment_detail(segment_id):
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
            tag_name = tag_info.get('name')
            if not tag_name:
                continue 

            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(
                    name=tag_name,
                    category=tag_info.get('category', '其他'), 
                    color=tag_info.get('color') 
                )
                db.session.add(tag)
            segment.tags.append(tag)
            
    db.session.commit()
    
    return jsonify({'success': True, 'segment_id': segment.id})

# Segment Delete API (DELETE)
@app.route('/api/segment/<int:segment_id>/delete', methods=['DELETE'])
def delete_segment_detail(segment_id):
    segment = Segment.query.get(segment_id)
    
    if not segment:
        return jsonify({'error': 'Segment not found'}), 404
        
    db.session.delete(segment)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Segment deleted'})

# 進階查詢功能
@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        data = request.get_json()
        query_type = data.get('query_type', 'symptom_to_cause')
        
        results = []
        
        if query_type == 'symptom_to_cause':
            # 從症狀找病因
            symptom_tags = data.get('symptom_tags', [])
            # 實現查詢邏輯...
            
        elif query_type == 'cause_to_treatment':
            # 從病因找治療方法
            cause_tags = data.get('cause_tags', [])
            # 實現查詢邏輯...
            
        return jsonify({'results': results})
    
    return render_template('search.html')

# 建立關聯
@app.route('/api/relation', methods=['POST'])
def create_relation():
    data = request.get_json()
    
    relation = QueryRelation(
        relation_type=data['relation_type'],
        source_type=data['source_type'],
        source_id=data['source_id'],
        target_type=data['target_type'],
        target_id=data['target_id'],
        strength=data.get('strength', 1.0),
        notes=data.get('notes', '')
    )
    
    db.session.add(relation)
    db.session.commit()
    
    return jsonify({'success': True, 'relation_id': relation.id})

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # This is for initial creation if not using migrations
    app.run(debug=True)
