import os
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename
from datetime import datetime

from models import db, Segment, Attachment
from config import ALLOWED_EXTENSIONS

attachment_bp = Blueprint('attachment', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_upload_folder():
    """確保上傳資料夾存在"""
    upload_folder = current_app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)
        # Consider logging this instead of printing, or make it configurable
        # print(f"創建上傳資料夾: {upload_folder}")

# 上傳附件
@attachment_bp.route('/upload', methods=['POST'])
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
            upload_folder_path = current_app.config['UPLOAD_FOLDER']
            
            ensure_upload_folder() # Call the local helper function
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
                file_path=filename, # This might be redundant if UPLOAD_FOLDER is always the same
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
                'filename': attachment.original_filename, # Return original for display
                'file_path': filename, # Return stored filename for linking
                'file_type': file_type
            }
            if processed_segment_id is not None: 
                response_data['segment_id'] = processed_segment_id
                
            return jsonify(response_data)
        else:
            return jsonify({'error': 'File type not allowed'}), 400
        
    except Exception as e:
        db.session.rollback()
        # Consider logging the error: current_app.logger.error(f"Upload failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route to serve uploaded files directly
@attachment_bp.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

# 添加别名路由以兼容模板中的引用
@attachment_bp.route('/serve_uploads/<path:filename>')
def serve_uploads(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

# Route to serve files based on Attachment records
@attachment_bp.route('/attachment/<int:attachment_id>')
def serve_attachment(attachment_id):
    attachment = Attachment.query.get(attachment_id)
    if not attachment: 
        return "Attachment not found", 404
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], attachment.filename, as_attachment=False)
