import os

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///knowledge.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
MAX_CONTENT_LENGTH = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'pdf', 'doc', 'docx'}
CATEGORY_COLORS = {
    'Technology': '#007bff',  # Blue
    'Science': '#28a745',  # Green
    'History': '#ffc107',  # Yellow
    'Art': '#dc3545',  # Red
    'Literature': '#17a2b8',  # Cyan
    'Mathematics': '#fd7e14',  # Orange
    'Geography': '#6f42c1',  # Indigo
    'Music': '#e83e8c',  # Pink
    'Philosophy': '#6610f2',  # Purple
    'Sports': '#20c997'  # Teal
}
