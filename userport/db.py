from flask import current_app, g
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi


def get_db():
    if 'db' not in g:
        # Create a new client and connect to the server
        client = MongoClient(
            current_app.config['MONGO_URI'], server_api=ServerApi('1'))
        g.db = client[current_app.config['MONGO_DB_NAME']]

    return g.db
