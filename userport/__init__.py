from . import auth
import os
from flask import Flask
from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env.


def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY='dev',
        MONGO_URI=os.environ['MONGO_URI'],
        MONGO_DB_NAME='db'
    )
    app.register_blueprint(auth.bp)

    return app
