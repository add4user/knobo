from . import auth
from . import application
import os
from flask import Flask
from celery import Celery, Task
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env.

csrf = CSRFProtect()


def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app


def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY='dev',
        MONGO_URI=os.environ['MONGO_URI'],
        MONGO_DB_NAME='db',
        CELERY=dict(
            broker_url="redis://localhost",
            task_ignore_result=True,
        ),
    )
    app.register_blueprint(auth.bp)
    app.register_blueprint(application.bp)

    # For inference POST requests, we will rely on API key based authentication.
    csrf.exempt(application.perform_inference)
    csrf.init_app(app)
    auth.login_manager.init_app(app)
    celery_init_app(app)

    app.add_url_rule('/', endpoint='index')

    return app
