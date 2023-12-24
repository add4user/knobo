from .app_factory import create_app

# This module is needed to initialize Celery worker from command line.

flask_app = create_app()
celery_app = flask_app.extensions["celery"]
