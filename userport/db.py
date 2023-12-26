from flask import current_app, g
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.collection import Collection
from userport.models import UserModel, OrganizationModel, SectionModel, UploadModel, UploadStatus
from datetime import datetime, timezone
from bson.objectid import ObjectId
from typing import Optional, Dict, List, Type
from userport.index.page_section_manager import PageSection
from queue import Queue


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


def _get_uploads() -> Collection:
    """
    Returns Uploads collection from database. All internal methods in this module should use this 
    helper to fetch the collection.
    """
    return _get_db()['uploads']


def _get_sections() -> Collection:
    """
    Returns Sections collection from database. All internal methods in this module should use this 
    helper to fetch the collection.
    """
    return _get_db()['sections']


def _get_api_keys() -> Collection:
    """
    Returns API Keys collection from database. All internal methods in this module should use this 
    helper to fetch the collection.
    """
    return _get_db()['api_keys']


def _get_upload_by_id(upload_id: str) -> Optional[UploadModel]:
    """
    Fetch Upload for given upload_id. Returns None if no such user exists.
    """
    uploads = _get_uploads()
    return _model_from_dict(UploadModel, uploads.find_one({"_id": ObjectId(upload_id)}))


def get_user_by_id(user_id: str) -> Optional[UserModel]:
    """
    Fetch user for given ID. Returns None if no such user exists.
    """
    users = _get_users()
    return _model_from_dict(UserModel, users.find_one({"_id": ObjectId(user_id)}))


def get_user_by_email(email: str) -> Optional[UserModel]:
    """
    Fetch user with given email from users collection. Returns None if no such user exists.
    """
    users = _get_users()
    return _model_from_dict(UserModel, users.find_one({"email": email}))


def get_org_by_domain(domain: str) -> Optional[OrganizationModel]:
    """
    Fetch organization with given domain. Returns None if no such user exists.
    """
    organizations = _get_organizations()
    organization_dict = organizations.find_one({"domain": domain})
    if not organization_dict:
        return None
    return OrganizationModel(**organization_dict)


def _model_from_dict(modelClass: Type, model_dict: Optional[Dict]) -> Optional[Type]:
    """
    Returns model of given class from given dictionary. Returns None of dictionary is None.
    """
    if not model_dict:
        return None
    return modelClass(**model_dict)


def _get_current_time() -> datetime:
    """
    Returns current time as datetime object in UTC timezone as expected by MongoDB per
    https://pymongo.readthedocs.io/en/stable/examples/datetimes.html
    """
    return datetime.now(tz=timezone.utc)


def _join_proper_nouns(proper_nouns_list: List[str]) -> str:
    """
    Helper that returns a string from given list of proper nouns.
    """
    return " ".join(proper_nouns_list)


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


def create_upload(user_id: str, url: str) -> str:
    """
    Creates an upload object and return associated ID.
    """
    user: Optional[UserModel] = get_user_by_id(user_id)
    if user == None:
        raise ValueError(f'User with id {user_id} does not exist for upload')

    upload_model = UploadModel(creator_id=user_id, created=_get_current_time(
    ), org_domain=user.org_domain, url=url, status=UploadStatus.IN_PROGRESS)

    uploads = _get_uploads()
    result = uploads.insert_one(upload_model.model_dump(exclude=['id']))
    return str(result.inserted_id)


def update_upload_status(upload_id: str, upload_status: UploadStatus, error_message: str = ""):
    """
    Updates upload with given id with given status. Error message is optional.
    Throws exception if upload is not found.
    """
    uploads = _get_uploads()
    if not uploads.find_one_and_update({'_id': ObjectId(upload_id)}, {'$set': {'status': upload_status, 'error_message': error_message}}):
        raise ValueError(
            f"No model found to update status with id: {upload_id}")


def get_upload_status(upload_id: str) -> UploadStatus:
    """
    Fetch upload status for given ID. Throws exception if upload not found.
    """
    upload: Optional[UploadModel] = _get_upload_by_id(upload_id)
    if not upload:
        raise ValueError(
            f"Did not find model with {upload_id} while fetching status")
    return upload.status


def insert_page_sections_transactionally(user_id: str, url: str, upload_id: str, root_page_section: PageSection):
    """
    Insert page sections in the tree of given root page section into Sections Collect in a 
    single transaction. All inserts are to the same collection and the parent_section_id field
    in each document forms the linkage between them.
    """
    assert root_page_section.is_root, f"Expected root section, got {root_page_section}"
    user: Optional[UserModel] = get_user_by_id(user_id)
    if user == None:
        raise ValueError(f'User with id {user_id} does not exist')

    current_time: datetime = _get_current_time()
    sections = _get_sections()
    client = _get_mongo_client()
    q = Queue()
    for child_page_section in root_page_section.child_sections:
        q.put((child_page_section, ""))
    with client.start_session() as session:
        with session.start_transaction():
            while not q.empty():
                qItem = q.get()
                page_section: PageSection = qItem[0]
                parent_section_id: str = qItem[1]
                proper_nouns_in_section = _join_proper_nouns(
                    page_section.proper_nouns_in_section)
                proper_nouns_in_doc = _join_proper_nouns(
                    page_section.proper_nouns_in_doc)

                section_model = SectionModel(upload_id=upload_id, org_domain=user.org_domain, parent_section_id=parent_section_id, url=url, text=page_section.text, summary=page_section.summary, prev_sections_context=page_section.prev_sections_context,
                                             summary_vector_embedding=page_section.summary_vector_embedding, proper_nouns_in_section=proper_nouns_in_section, proper_nouns_in_doc=proper_nouns_in_doc, creator_id=user_id, created=current_time)
                result = sections.insert_one(
                    section_model.model_dump(exclude=['id']))
                section_id = str(result.inserted_id)

                for child_page_section in page_section.child_sections:
                    q.put((child_page_section, section_id))
