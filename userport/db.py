from flask import current_app, g
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.collection import Collection
from userport.models import UserModel, OrganizationModel
from datetime import datetime, timezone
from bson.objectid import ObjectId
from typing import Optional, Dict


def _get_mongo_client() -> MongoClient:
    if 'mongo_client' not in g:
        # Create a new client and connect to the server
        client = MongoClient(
            current_app.config['MONGO_URI'], server_api=ServerApi('1'))
        g.mongo_client = client

    return g.mongo_client


def _get_db():
    mongo_client = _get_mongo_client()
    return mongo_client[current_app.config['MONGO_DB_NAME']]


def _get_users() -> Collection:
    """
    Returns Users collection from database. All internal methods in this module should use this 
    helper to fetch the collection.
    """
    return _get_db()['users']


def _get_organizations() -> Collection:
    """
    Returns Organizations collection from database. All internal methods in this module should use this 
    helper to fetch the collection.
    """
    return _get_db()['organizations']


def _get_api_keys() -> Collection:
    """
    Returns API Keys collection from database. All internal methods in this module should use this 
    helper to fetch the collection.
    """
    return _get_db()['api_keys']


def get_user_by_id(user_id: str) -> Optional[UserModel]:
    """
    Fetch user for given ID. Returns None if no such user exists.
    """
    users = _get_users()
    return _user_model_from_dict(users.find_one({"_id": ObjectId(user_id)}))


def get_user_by_email(email: str) -> Optional[UserModel]:
    """
    Fetch user with given email from users collection. Returns None if no such user exists.
    """
    users = _get_users()
    return _user_model_from_dict(users.find_one({"email": email}))


def get_org_by_domain(domain: str) -> Optional[OrganizationModel]:
    """
    Fetch organization with given domain. Returns None if no such user exists.
    """
    organizations = _get_organizations()
    organization_dict = organizations.find_one({"domain": domain})
    if not organization_dict:
        return None
    return OrganizationModel(**organization_dict)


def _user_model_from_dict(user_dict: Optional[Dict]) -> Optional[UserModel]:
    if not user_dict:
        return None
    return UserModel(**user_dict)


def _get_current_time() -> datetime:
    """
    Returns current time as datetime object in UTC timezone as expected by MongoDB per
    https://pymongo.readthedocs.io/en/stable/examples/datetimes.html
    """
    return datetime.now(tz=timezone.utc)


def create_user_and_organization_transactionally(user_model: UserModel, organization_model: OrganizationModel):
    """
    Creates user document and Organization transactionally.
    """
    assert user_model.id == None, f"User Model has non empty ID {user_model.id}"
    assert organization_model.id == None, f"Organization Model has non empty ID {user_model.id}"

    current_time: datetime = _get_current_time()
    user_model.created = current_time
    user_model.last_updated = current_time
    organization_model.created = current_time
    organization_model.last_updated = current_time

    user_model_dict = user_model.model_dump(exclude=['id'])
    organization_model_dict = organization_model.model_dump(exclude=['id'])

    users = _get_users()
    organizations = _get_organizations()

    # Transactional insertion of both user and organization data.
    client = _get_mongo_client()
    with client.start_session() as session:
        with session.start_transaction():
            users.insert_one(user_model_dict)
            organizations.insert_one(organization_model_dict)
