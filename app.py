import os
import logging
from flask import Flask, render_template # render_template for error handlers
from flask_migrate import Migrate
from dotenv import load_dotenv

# Import db instance from models.py
from models import db # Assuming db is initialized in models.py as SQLAlchemy()

# Blueprints - to be imported within create_app to avoid circular dependencies if they import 'app'
# For now, direct imports are fine as blueprints should import 'db' from 'models' not 'app'

def create_app():
    """Application factory function."""
    load_dotenv()  # Load environment variables

    app = Flask(__name__)

    # Load configuration from config.py
    app.config.from_object('config')

    # Initialize extensions
    db.init_app(app)
    Migrate(app, db)

    # Configure basic logging (optional, as blueprints might have their own)
    # If you want global logging configured here:
    log_level_str = os.environ.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    app.logger.setLevel(log_level) # Set Flask app logger level
    logger = logging.getLogger(__name__) # Get logger for this file
    logger.info(f"App initialized with log level: {log_level_str}")


    # Import and Register Blueprints
    from blueprints.main_routes import main_bp
    from blueprints.session_routes import session_bp
    from blueprints.segment_routes import segment_bp
    from blueprints.attachment_routes import attachment_bp
    from blueprints.tag_routes import tag_bp
    from blueprints.search_routes import search_bp # search_bp now imports UnifiedSearchService from services
    from blueprints.vector_db_routes import vector_db_bp
    from blueprints.relation_routes import relation_bp
    from blueprints.statistics_routes import statistics_bp
    from blueprints.batch_routes import batch_bp
    from blueprints.llm_routes import llm_bp
    from blueprints.utility_routes import utility_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(session_bp)
    app.register_blueprint(segment_bp)
    app.register_blueprint(attachment_bp)
    app.register_blueprint(tag_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(vector_db_bp)
    app.register_blueprint(relation_bp)
    app.register_blueprint(statistics_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(llm_bp) # url_prefix is already in llm_routes.py
    app.register_blueprint(utility_bp) # url_prefix is already in utility_routes.py

    # Error Handlers
    @app.errorhandler(404)
    def not_found_error(error):
        logger.warning(f"404 error: {error} for request {request.url}")
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"500 error: {error} for request {request.url}", exc_info=True)
        # db.session.rollback() # Ensure db is accessible here if you need to rollback
        # It's generally better to handle session rollbacks closer to where db operations fail,
        # e.g., in the route handlers themselves, or via a request teardown context.
        # However, if an error happens after a db operation but before commit, this can be a safety net.
        # For now, assuming individual routes/services handle their rollbacks.
        return render_template('500.html'), 500

    logger.info("Flask app created and configured.")
    return app

if __name__ == '__main__':
    app = create_app()
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.environ.get('PORT', 5000))
    app.logger.info(f"Starting Flask app with debug_mode={debug_mode} on port={port}")
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
