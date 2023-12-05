from . import auth
import os
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env.

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY='dev',
        MONGO_URI=os.environ['MONGO_URI'],
        MONGO_DB_NAME='db'
    )
    app.register_blueprint(auth.bp)
    csrf.init_app(app)
    auth.login_manager.init_app(app)

    return app
