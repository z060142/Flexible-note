import os
import logging
from flask import Blueprint, request, jsonify
from datetime import datetime # Though not directly used in these routes, LLMCourseService might use it
from dotenv import load_dotenv

# Important: Ensure models are imported if LLMCourseService.save_processed_course interacts with them directly.
# Based on app.py, Session is used in save_llm_course for vector DB sync.
from models import db, Session 
from llm_service import LLMCourseService

# Initialize logger
logger = logging.getLogger(__name__)

# Load environment variables at the start, especially for get_llm_config and update_llm_config
load_dotenv()

# Import vector search related services safely
try:
    from vector_service import get_chroma_manager, VECTOR_SEARCH_ENABLED
except ImportError as e:
    logger.warning(f"Vector search service import failed in llm_routes: {e}")
    VECTOR_SEARCH_ENABLED = False
    def get_chroma_manager():
        logger.error("get_chroma_manager called but vector search is disabled in llm_routes.")
        # Return a mock manager that has an add_session method for save_llm_course
        class MockChromaManager:
            def add_session(self, session_obj):
                 logger.error(f"MockChromaManager.add_session called with session: {session_obj.id if session_obj else 'None'}")
        return MockChromaManager()


# Create Blueprint with URL prefix
llm_bp = Blueprint('llm_api', __name__, url_prefix='/api/llm')

# --- LLM API Routes ---
@llm_bp.route('/test-ollama', methods=['POST'])
def test_ollama_connection():
    """測試 Ollama 連接"""
    try:
        data = request.get_json()
        if not data or not data.get('baseUrl'):
            return jsonify({'success': False, 'error': '請提供 Ollama 服務地址'}), 400
        
        # LLMCourseService is already imported
        result = LLMCourseService.test_ollama_connection(data['baseUrl'])
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error testing Ollama connection: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@llm_bp.route('/process-course', methods=['POST'])
def process_course_with_llm():
    """使用 LLM 處理課程文檔"""
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': '沒有上傳文件'}), 400
        
        files = request.files.getlist('files')
        if not files or not any(f.filename for f in files):
            return jsonify({'success': False, 'error': '沒有選擇有效文件'}), 400
        
        form_data = {
            'apiProvider': request.form.get('apiProvider'),
            'courseTitle': request.form.get('courseTitle'),
            'courseDate': request.form.get('courseDate'),
            'courseDomain': request.form.get('courseDomain'),
            'additionalTags': request.form.get('additionalTags'),
            'apiKey': request.form.get('apiKey'),
            'baseUrl': request.form.get('baseUrl'),
            'model': request.form.get('model')
        }
        
        if not form_data['apiProvider']: return jsonify({'success': False, 'error': '請選擇 API 提供者'}), 400
        if not form_data['courseTitle']: return jsonify({'success': False, 'error': '請輸入課程標題'}), 400
        if form_data['apiProvider'] in ['openai', 'gemini'] and not form_data['apiKey']:
            return jsonify({'success': False, 'error': 'API Key 不能為空'}), 400
        
        processed_course = LLMCourseService.process_course_files(files, form_data)
        
        result_data = {
            'courseTitle': processed_course.courseTitle,
            'overview': processed_course.overview,
            'tags': processed_course.tags,
            'segments': [{'type': seg.type, 'title': seg.title, 'content': seg.content, 'tags': seg.tags} for seg in processed_course.segments],
            '_courseInfo': form_data 
        }
        return jsonify({'success': True, 'data': result_data})
        
    except Exception as e:
        logger.error(f"LLM 課程處理失敗: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@llm_bp.route('/save-course', methods=['POST'])
def save_llm_course():
    """保存 LLM 處理後的課程"""
    try:
        data = request.get_json()
        if not data: return jsonify({'success': False, 'error': '沒有課程數據'}), 400
        
        course_info = data.get('_courseInfo', {})
        session_id = LLMCourseService.save_processed_course(data, course_info) # Depends on db, Session, Tag, Segment
        
        if VECTOR_SEARCH_ENABLED:
            try:
                chroma_manager = get_chroma_manager()
                if chroma_manager: # Ensure manager is not None (especially if mock was used)
                    session_obj = Session.query.get(session_id) # session_obj instead of session to avoid conflict
                    if session_obj:
                        chroma_manager.add_session(session_obj)
                    else:
                        logger.warning(f"Could not find session with ID {session_id} for vector DB sync.")
            except Exception as e:
                logger.warning(f"向量數據庫同步失敗 (llm_routes): {e}")
        
        return jsonify({'success': True, 'session_id': session_id, 'message': '課程保存成功'})
    except Exception as e:
        db.session.rollback() # Ensure rollback on error during save
        logger.error(f"保存 LLM 課程失敗: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@llm_bp.route('/config', methods=['GET'])
def get_llm_config():
    """獲取 LLM API 配置"""
    try:
        config = {
            'openai': {'apiKey': os.getenv('OPENAI_API_KEY', ''), 'baseUrl': os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'), 'model': os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')},
            'gemini': {'apiKey': os.getenv('GEMINI_API_KEY', ''), 'model': os.getenv('GEMINI_MODEL', 'gemini-pro')},
            'ollama': {'baseUrl': os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'), 'model': os.getenv('OLLAMA_MODEL', 'llama2')},
            'defaultProvider': os.getenv('DEFAULT_API_PROVIDER', 'openai')
        }
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        logger.error(f"Error getting LLM config: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@llm_bp.route('/config', methods=['POST'])
def update_llm_config():
    """更新 LLM API 配置到 .env 檔案"""
    try:
        data = request.get_json()
        if not data: return jsonify({'success': False, 'error': '沒有配置數據'}), 400
        
        config_data = data.get('config', {}) # Renamed to avoid conflict
        
        env_path = '.env'
        env_lines = []
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                env_lines = f.readlines()
        
        updates = {}
        if 'openai' in config_data:
            updates['OPENAI_API_KEY'] = config_data['openai'].get('apiKey', os.getenv('OPENAI_API_KEY', ''))
            updates['OPENAI_BASE_URL'] = config_data['openai'].get('baseUrl', os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'))
            updates['OPENAI_MODEL'] = config_data['openai'].get('model', os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'))
        if 'gemini' in config_data:
            updates['GEMINI_API_KEY'] = config_data['gemini'].get('apiKey', os.getenv('GEMINI_API_KEY', ''))
            updates['GEMINI_MODEL'] = config_data['gemini'].get('model', os.getenv('GEMINI_MODEL', 'gemini-pro'))
        if 'ollama' in config_data:
            updates['OLLAMA_BASE_URL'] = config_data['ollama'].get('baseUrl', os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'))
            updates['OLLAMA_MODEL'] = config_data['ollama'].get('model', os.getenv('OLLAMA_MODEL', 'llama2'))
        if 'defaultProvider' in config_data:
            updates['DEFAULT_API_PROVIDER'] = config_data['defaultProvider']

        updated_lines = []
        updated_keys = set()
        for line in env_lines:
            line = line.rstrip('\n\r')
            if '=' in line and not line.strip().startswith('#'):
                key = line.split('=', 1)[0].strip() # Split only on the first '='
                if key in updates:
                    updated_lines.append(f'{key}={updates[key]}\n')
                    updated_keys.add(key)
                else:
                    updated_lines.append(line + '\n')
            else:
                updated_lines.append(line + '\n')
        
        for key, value in updates.items():
            if key not in updated_keys:
                updated_lines.append(f'{key}={value}\n')
        
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
        
        load_dotenv(override=True) # Reload .env variables
        
        return jsonify({'success': True, 'message': 'API 配置已保存到 .env 檔案'})
    except Exception as e:
        logger.error(f"更新 LLM 配置失敗: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
