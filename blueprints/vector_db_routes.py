import logging
from flask import Blueprint, jsonify

# Initialize logger
logger = logging.getLogger(__name__)

# Import vector search related services safely
try:
    from vector_service import get_chroma_manager, sync_existing_data, VECTOR_SEARCH_ENABLED
except ImportError as e:
    logger.warning(f"Vector search service import failed: {e}")
    logger.warning("Proceeding with vector search disabled. Install chromadb and sentence-transformers if needed.")
    VECTOR_SEARCH_ENABLED = False
    # Mock functions if import fails
    def get_chroma_manager():
        logger.error("get_chroma_manager called but vector search is disabled.")
        # Return a mock manager that has a get_collection_stats method
        class MockChromaManager:
            def get_collection_stats(self):
                logger.error("MockChromaManager.get_collection_stats called")
                return {"error": "Vector search is disabled"}
        return MockChromaManager()

    def sync_existing_data():
        logger.error("sync_existing_data called but vector search is disabled.")
        raise RuntimeError("Vector search functionality is not available.")

vector_db_bp = Blueprint('vector_db', __name__)

# 向量數據庫狀態 API
@vector_db_bp.route('/api/vector/status', methods=['GET'])
def vector_status():
    """向量數據庫狀態檢查"""
    if not VECTOR_SEARCH_ENABLED:
        return jsonify({'enabled': False, 'message': 'Vector search dependencies not installed or not fully functional'})
    
    try:
        chroma_manager = get_chroma_manager()
        if chroma_manager is None: # Should ideally be caught by VECTOR_SEARCH_ENABLED
             return jsonify({'enabled': True, 'status': 'error', 'error': 'Chroma manager not available'})
        stats = chroma_manager.get_collection_stats()
        return jsonify({
            'enabled': True,
            'status': 'healthy',
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error getting vector status: {str(e)}")
        return jsonify({
            'enabled': True, # It's enabled, but there was an error
            'status': 'error',
            'error': str(e)
        })

# 數據同步 API
@vector_db_bp.route('/api/vector/sync', methods=['POST'])
def sync_vector_db_route(): # Renamed to avoid conflict if sync_vector_db is also imported directly
    """同步數據到向量數據庫"""
    if not VECTOR_SEARCH_ENABLED:
        return jsonify({'success': False, 'error': 'Vector search not enabled'}), 503
    
    try:
        sync_existing_data() # This is the imported function
        return jsonify({'success': True, 'message': '數據同步完成'})
    except RuntimeError as r_err: # Catch specific error from mock
        logger.error(f"Vector sync runtime error: {str(r_err)}")
        return jsonify({'success': False, 'error': str(r_err)}), 503
    except Exception as e:
        logger.error(f"Error during vector sync: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
