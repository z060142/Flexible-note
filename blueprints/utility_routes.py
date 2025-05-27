import os
import logging
from flask import Blueprint, jsonify, current_app
from sqlalchemy import text
from datetime import datetime

from models import db

# Initialize logger
logger = logging.getLogger(__name__)

# Create Blueprint with /api prefix as the original route is /api/health
utility_bp = Blueprint('utility_api', __name__, url_prefix='/api')

# Moved Flask Route
@utility_bp.route('/health', methods=['GET'])
def health_check():
    """系統健康檢查"""
    try:
        # 檢查資料庫連接
        db.session.execute(text('SELECT 1'))
        
        # 檢查上傳資料夾
        # UPLOAD_FOLDER is expected to be in current_app.config
        upload_folder = current_app.config.get('UPLOAD_FOLDER') 
        if not upload_folder:
            logger.warning("UPLOAD_FOLDER not configured in current_app.config")
            # Return a warning but still indicate partial health if DB is okay
            return jsonify({
                'status': 'warning',
                'message': 'Upload folder not configured',
                'timestamp': datetime.utcnow().isoformat(),
                'database': 'connected',
                'upload_folder': 'not_configured'
            }), 200 # Return 200 as the API endpoint itself is working

        if not os.path.exists(upload_folder):
            logger.warning(f"Upload folder {upload_folder} not found.")
            return jsonify({
                'status': 'warning',
                'message': 'Upload folder not found',
                'timestamp': datetime.utcnow().isoformat(),
                'database': 'connected', # DB check passed before this
                'upload_folder': 'not_found'
            }), 200
        
        return jsonify({
            'status': 'healthy',
            'message': 'System is running normally',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected',
            'upload_folder': 'accessible'
        }), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e), # Provide the actual error for debugging
            'timestamp': datetime.utcnow().isoformat()
        }), 500
