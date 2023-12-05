from flask import current_app, g
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.collection import Collection
from userport.models import UserModel
from datetime import datetime, timezone
from bson.objectid import ObjectId
from typing import Optional, Dict


def get_db():
    if 'db' not in g:
        # Create a new client and connect to the server
        client = MongoClient(
            current_app.config['MONGO_URI'], server_api=ServerApi('1'))
        g.db = client[current_app.config['MONGO_DB_NAME']]

    return g.db


def get_current_time() -> datetime:
    """
    Returns current time as datetime object in UTC timezone as expected by MongoDB per
    https://pymongo.readthedocs.io/en/stable/examples/datetimes.html
    """
    return datetime.now(tz=timezone.utc)


def get_users() -> Collection:
    """
    Return Users collection from database. All internal methods in this module should use this 
    helper to fetch the collection.
    """
    return get_db()['users']


def get_user_by_id(user_id: str) -> Optional[UserModel]:
    """
    Fetch user for given ID. Returns None if no such user exists.
    """
    users = get_users()
    return _user_model_from_dict(users.find_one({"_id": ObjectId(user_id)}))


def get_user_by_email(email: str) -> Optional[UserModel]:
    """
    Fetch user with given email from users collection. Returns None if no such user exists.
    """
    users = get_users()
    return _user_model_from_dict(users.find_one({"email": email}))


def _user_model_from_dict(user_dict: Optional[Dict]) -> Optional[UserModel]:
    if not user_dict:
        return None
    return UserModel(**user_dict)


def create_user(user_model: UserModel):
    """
    Creates user object in Database from given user model.
    """
    assert user_model.id == None, f"User Model has non empty ID {user_model.id}"
    users = get_users()

    user_model_dict = user_model.model_dump(exclude=['id'])
    result = users.insert_one(user_model_dict)
    print("created user: ", result.inserted_id)
