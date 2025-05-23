import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from datetime import datetime
import json
from sqlalchemy import func, and_ 

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
        
        tag_names = data.get('tags', [])
        for tag_name in tag_names:
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name, category=data.get('tag_category', '領域'))
            session.tags.append(tag)
        
        db.session.add(session)
        db.session.commit()
        
        return jsonify({'success': True, 'session_id': session.id})
    
    return render_template('session_form.html', datetime=datetime)

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
            
        session.tags.clear() 
        tag_names = data.get('tags', [])
        tag_category = data.get('tag_category', '領域') 
        
        for tag_name in tag_names:
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name, category=tag_category)
                db.session.add(tag) 
            session.tags.append(tag)
            
        db.session.commit()
        return jsonify({'success': True, 'session_id': session.id})
        
    all_tags = Tag.query.all()
    return render_template('session_edit_form.html', session=session, all_tags=all_tags)

# 新增段落
@app.route('/session/<int:session_id>/segment', methods=['POST'])
def add_segment(session_id):
    session = Session.query.get_or_404(session_id)
    data = request.get_json()
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
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(original_filename)}"
        upload_folder_path = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder_path, exist_ok=True)
        file_path_on_disk = os.path.join(upload_folder_path, filename)
        file.save(file_path_on_disk)
        
        ext = filename.rsplit('.', 1)[1].lower()
        file_type = 'document' 
        if ext in ['png', 'jpg', 'jpeg', 'gif']: file_type = 'image'
        elif ext in ['mp4', 'avi']: file_type = 'video'
        
        attachment = Attachment(
            filename=filename, original_filename=original_filename, file_type=file_type,
            file_path=filename, description=request.form.get('description', '')
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
        
        response_data = {'success': True, 'attachment_id': attachment.id, 'filename': attachment.original_filename}
        if processed_segment_id is not None: response_data['segment_id'] = processed_segment_id
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
    if not attachment: return "Attachment not found", 404
    return send_from_directory(app.config['UPLOAD_FOLDER'], attachment.filename, as_attachment=False)

# Tag Management Page
@app.route('/tags/manage')
def manage_tags():
    tags = Tag.query.order_by(Tag.category, Tag.name).all()
    return render_template('tag_management.html', tags=tags)

# API Routes
@app.route('/api/tags', methods=['GET'])
def get_tags():
    category = request.args.get('category')
    query = Tag.query
    if category: query = query.filter_by(category=category)
    tags = query.all()
    return jsonify([tag.to_dict() for tag in tags])

@app.route('/api/tags/search', methods=['GET'])
def search_tags():
    q = request.args.get('q', '')
    tags = Tag.query.filter(Tag.name.contains(q)).limit(10).all()
    return jsonify([tag.to_dict() for tag in tags])

@app.route('/api/tag/<int:tag_id>/update', methods=['POST'])
def update_tag(tag_id):
    tag = Tag.query.get(tag_id)
    if not tag: return jsonify({'error': 'Tag not found'}), 404
    data = request.get_json()
    if not data: return jsonify({'error': 'No input data provided'}), 400

    new_name = data.get('name', tag.name).strip()
    new_category = data.get('category', tag.category).strip()
    
    if new_name != tag.name or new_category != tag.category: 
        existing_tag = Tag.query.filter(Tag.name == new_name, Tag.category == new_category).first()
        if existing_tag and existing_tag.id != tag_id: 
             return jsonify({'error': f"Tag name '{new_name}' already exists in category '{new_category}'."}), 400

    tag.name = new_name
    tag.category = new_category
    tag.color = data.get('color', tag.color)
    tag.description = data.get('description', tag.description)
    
    db.session.commit()
    return jsonify({'success': True, 'tag': tag.to_dict()})

@app.route('/api/tag/<int:tag_id>/delete', methods=['DELETE'])
def delete_tag(tag_id):
    tag = Tag.query.get(tag_id)
    if not tag: return jsonify({'error': 'Tag not found'}), 404
    db.session.delete(tag)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Tag deleted'})

@app.route('/api/segment/<int:segment_id>', methods=['GET'])
def get_segment_detail(segment_id):
    segment = Segment.query.get(segment_id) 
    if not segment: return jsonify({'error': 'Segment not found'}), 404
    segment_data = {
        'id': segment.id, 'session_id': segment.session_id,
        'segment_type': segment.segment_type, 'title': segment.title,
        'content': segment.content, 'tags': [tag.to_dict() for tag in segment.tags]
    }
    return jsonify(segment_data)

@app.route('/api/segment/<int:segment_id>/update', methods=['POST']) 
def update_segment_detail(segment_id):
    segment = Segment.query.get(segment_id)
    if not segment: return jsonify({'error': 'Segment not found'}), 404
    data = request.get_json()
    if not data: return jsonify({'error': 'No input data provided'}), 400
    segment.segment_type = data.get('segment_type', segment.segment_type)
    segment.title = data.get('title', segment.title)
    segment.content = data.get('content', segment.content)
    if 'tags' in data: 
        segment.tags.clear()
        tag_data_list = data.get('tags', [])
        for tag_info in tag_data_list:
            tag_name = tag_info.get('name')
            if not tag_name: continue 
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name, category=tag_info.get('category', '其他'), color=tag_info.get('color'))
                db.session.add(tag)
            segment.tags.append(tag)
    db.session.commit()
    return jsonify({'success': True, 'segment_id': segment.id})

@app.route('/api/segment/<int:segment_id>/delete', methods=['DELETE'])
def delete_segment_detail(segment_id):
    segment = Segment.query.get(segment_id)
    if not segment: return jsonify({'error': 'Segment not found'}), 404
    db.session.delete(segment)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Segment deleted'})

@app.route('/api/session/<int:session_id>/export', methods=['GET'])
def export_session_json(session_id):
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

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        data = request.get_json()
        query_type = data.get('query_type', 'symptom_to_cause')
        results = []
        
        if query_type == 'symptom_to_cause':
            symptom_tag_names = data.get('symptom_tags', [])
            location_name = data.get('location', None)
            if not symptom_tag_names: return jsonify({'results': [], 'message': 'Please provide at least one symptom tag.'})
            query = db.session.query(Segment).distinct().join(Segment.tags).filter(Tag.category == '症狀', Tag.name.in_(symptom_tag_names))
            if location_name: query = query.filter(Segment.tags.any(and_(Tag.category == '位置', Tag.name.contains(location_name))))
            found_segments = query.all()
            for segment in found_segments:
                potential_cause_tags, matched_symptoms_on_segment = [], []
                for tag in segment.tags:
                    if tag.category == '病因': potential_cause_tags.append(tag.to_dict())
                    if tag.name in symptom_tag_names and tag.category == '症狀': matched_symptoms_on_segment.append(tag.to_dict())
                if segment.session:
                    for tag in segment.session.tags:
                        if tag.category == '病因' and not any(pct['id'] == tag.id for pct in potential_cause_tags):
                            potential_cause_tags.append(tag.to_dict())
                if potential_cause_tags: 
                    results.append({
                        "segment_id": segment.id, "segment_title": segment.title,
                        "segment_content_preview": (segment.content[:100] + "...") if segment.content else "",
                        "session_id": segment.session_id, "session_title": segment.session.title if segment.session else "N/A",
                        "potential_cause_tags": potential_cause_tags, "matched_symptoms": matched_symptoms_on_segment
                    })
            
        elif query_type == 'cause_to_treatment':
            cause_tag_names = data.get('cause_tags', [])
            preferred_domain_name = data.get('preferred_domain', None)
            if not cause_tag_names: return jsonify({'results': [], 'message': 'Please provide at least one cause tag.'})
            query = db.session.query(Segment).distinct().join(Segment.tags).filter(Tag.category == '病因', Tag.name.in_(cause_tag_names))
            if preferred_domain_name:
                query = query.join(Session, Segment.session_id == Session.id)\
                             .filter(Session.tags.any(and_(Tag.category == '領域', Tag.name == preferred_domain_name)))
            found_segments = query.all()
            for segment in found_segments:
                potential_treatment_tags, matched_causes_on_segment = [], []
                for tag in segment.tags:
                    if tag.category in ['治療', '手法']: potential_treatment_tags.append(tag.to_dict())
                    if tag.name in cause_tag_names and tag.category == '病因': matched_causes_on_segment.append(tag.to_dict())
                if potential_treatment_tags or segment.segment_type == '治療':
                    results.append({
                        "segment_id": segment.id, "segment_title": segment.title,
                        "segment_content_preview": (segment.content[:100] + "...") if segment.content else "",
                        "segment_type": segment.segment_type, "session_id": segment.session_id,
                        "session_title": segment.session.title if segment.session else "N/A",
                        "potential_treatment_tags": potential_treatment_tags, "matched_causes": matched_causes_on_segment
                    })
        
        elif query_type == 'method_analysis':
            method_name = data.get('method_name', None)
            if not method_name: return jsonify({'results': [], 'message': 'Please provide a method name.'})
            method_tag = Tag.query.filter_by(name=method_name, category='手法').first()
            if not method_tag: return jsonify({'results': [], 'message': f"Method tag '{method_name}' not found."})
            segments_using_method = Segment.query.join(Segment.tags).filter(Tag.id == method_tag.id).all()
            unique_symptom_tags, unique_cause_tags, unique_cooccurring_methods, unique_location_tags = {}, {}, {}, {}
            for seg in segments_using_method:
                for tag in seg.tags:
                    if tag.category == '症狀': unique_symptom_tags[tag.id] = tag
                    elif tag.category == '病因': unique_cause_tags[tag.id] = tag
                    elif tag.category == '手法' and tag.id != method_tag.id: unique_cooccurring_methods[tag.id] = tag
                    elif tag.category == '位置': unique_location_tags[tag.id] = tag
            results.append({
                "method_name": method_tag.name, "method_id": method_tag.id, "description": method_tag.description,
                "applicable_symptoms": [t.to_dict() for t in unique_symptom_tags.values()],
                "treated_causes": [t.to_dict() for t in unique_cause_tags.values()],
                "common_locations": [t.to_dict() for t in unique_location_tags.values()],
                "related_methods": [t.to_dict() for t in unique_cooccurring_methods.values()],
                "example_segments": [{"segment_id": s.id, "segment_title": s.title, "session_id": s.session_id, 
                                      "session_title": s.session.title if s.session else "N/A"} for s in segments_using_method[:5]]
            })

        return jsonify({'results': results})
    
    return render_template('search.html')

@app.route('/api/relation', methods=['POST'])
def create_relation():
    data = request.get_json()
    relation = QueryRelation(
        relation_type=data['relation_type'], source_type=data['source_type'],
        source_id=data['source_id'], target_type=data['target_type'],
        target_id=data['target_id'], strength=data.get('strength', 1.0),
        notes=data.get('notes', '')
    )
    db.session.add(relation)
    db.session.commit()
    return jsonify({'success': True, 'relation_id': relation.id})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
