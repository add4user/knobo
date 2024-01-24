from flask import current_app, g
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.collection import Collection
from userport.models import (
    UserModel,
    OrganizationModel,
    SectionModel,
    UploadModel,
    UploadStatus,
    APIKeyModel,
    VectorSearchSectionResult,
    InferenceResultModel,
    ChatMessageModel,
    MessageCreatorType
)
from userport.slack_models import SlackUpload, SlackUploadStatus
from datetime import datetime, timezone
from bson.objectid import ObjectId
from typing import Optional, Dict, List, Type
from userport.index.page_section_manager import PageSection
from queue import Queue


class NotFoundException(Exception):
    pass


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


def _get_vector_index_name() -> str:
    """
    Returns name of vector index to use to perform search.
    """
    return "sections_vector_index"


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


def _get_slack_uploads() -> Collection:
    """
    Returns Slack Uploads collection from database. All internal methods in this module should use this 
    helper to fetch the collection.
    """
    return _get_db()['slack_uploads']


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


def _get_inference_results() -> Collection:
    """
    Returns Inference Results collection from database. All internal methods in this module should use this 
    helper to fetch the collection.
    """
    return _get_db()['inference_results']


def _get_chat_messages() -> Collection:
    """
    Returns Chat Messages collection from database. All internal methods in this module should use this 
    helper to fetch the collection.
    """
    return _get_db()['chat_messages']


def get_upload_by_id(upload_id: str) -> UploadModel:
    """
    Fetch Upload for given upload id. Throws exception if upload model does not exist.
    """
    uploads = _get_uploads()
    upload_model = _model_from_dict(
        UploadModel, uploads.find_one({"_id": ObjectId(upload_id)}))
    if not upload_model:
        raise ValueError(
            f"Did not find model with {upload_id}")
    return upload_model


def get_user_by_id(user_id: str) -> UserModel:
    """
    Fetch user for given ID. Throws Exception no such user exists.
    """
    users = _get_users()
    user = _model_from_dict(
        UserModel, users.find_one({"_id": ObjectId(user_id)}))
    if user == None:
        raise NotFoundException(f'User with id {user_id} does not exist')
    return user


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
    user: UserModel = get_user_by_id(user_id)

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
        raise NotFoundException(
            f"No model found to update status with id: {upload_id}")


def list_uploads_by_org_domain(org_domain: str) -> List[UploadModel]:
    """
    List all uploads for a given org domain. Not paginating for now.
    """
    upload_model_list: List[UploadModel] = []
    uploads = _get_uploads()
    for upload_model_dict in uploads.find({"org_domain": org_domain}):
        upload_model_list.append(UploadModel(**upload_model_dict))
    return upload_model_list


def upload_already_has_sections(upload_id: str) -> bool:
    """
    Returns true if upload already has sections associated with it else returns false.
    """
    sections = _get_sections()
    section_dict = sections.find_one({"upload_id": upload_id})
    return True if section_dict else False


def insert_page_sections_transactionally(user_id: str, url: str, upload_id: str, root_page_section: PageSection):
    """
    Insert page sections in the tree of given root page section into Sections Collect in a 
    single transaction. All inserts are to the same collection and the parent_section_id field
    in each document forms the linkage between them.
    """
    assert root_page_section.is_root, f"Expected root section, got {root_page_section}"
    user: UserModel = get_user_by_id(user_id)

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

                section_model = SectionModel(upload_id=upload_id, org_domain=user.org_domain, parent_section_id=parent_section_id, url=url, text=page_section.text, summary=page_section.summary, prev_sections_context=page_section.prev_sections_context,
                                             summary_vector_embedding=page_section.summary_vector_embedding, proper_nouns_in_section=page_section.proper_nouns_in_section, proper_nouns_in_doc=page_section.proper_nouns_in_doc, creator_id=user_id, created=current_time)
                result = sections.insert_one(
                    section_model.model_dump(exclude=['id']))
                section_id = str(result.inserted_id)

                for child_page_section in page_section.child_sections:
                    q.put((child_page_section, section_id))


def delete_upload_and_sections_transactionally(upload_id: str):
    """
    Delete upload and all associated sections in a single transaction. 
    """
    client = _get_mongo_client()
    uploads = _get_uploads()
    sections = _get_sections()
    with client.start_session() as session:
        with session.start_transaction():
            deleted_result = sections.delete_many({'upload_id': upload_id})
            deleted_result = uploads.delete_one({'_id': ObjectId(upload_id)})
            if deleted_result.deleted_count != 1:
                raise NotFoundException(
                    f"Expected 1 doc to be deleted, got {deleted_result.deleted_count} deleted")


def create_slack_upload(creator_id: str, team_id: str, view_id: str, response_url: str) -> str:
    """
    Creates an Slack upload object and returns created ID.
    """
    current_time = _get_current_time()
    upload = SlackUpload(creator_id=creator_id, team_id=team_id, view_id=view_id, response_url=response_url,
                         status=SlackUploadStatus.NOT_STARTED, created_time=current_time, last_updated_time=current_time)

    slack_uploads = _get_slack_uploads()
    result = slack_uploads.insert_one(upload.model_dump(exclude=['id']))
    return str(result.inserted_id)


def get_slack_upload(view_id: str) -> SlackUpload:
    """
    Returns True if Slack Upload associated with given View ID is in progress and False otherwise.
    """
    uploads = _get_slack_uploads()
    upload_model: Optional[SlackUpload] = _model_from_dict(
        SlackUpload, uploads.find_one({"view_id": view_id}))
    if upload_model == None:
        raise NotFoundException(
            f'No Slack Upload found for View ID: {view_id}')
    return upload_model


def update_slack_upload(view_id: str, heading: str, text: str):
    """
    Updates Slack upload with given View id with heading and text values. Throws exception if upload is not found.
    """
    uploads = _get_slack_uploads()
    if not uploads.find_one_and_update(
        {'view_id': view_id},
        {'$set': {
            'status': SlackUploadStatus.IN_PROGRESS,
            'heading': heading,
            'text': text,
            'last_updated_time': _get_current_time(),
        }
        }
    ):
        raise NotFoundException(
            f"No model found to update status with View ID: {view_id}")


def delete_slack_upload(view_id: str):
    """
    Delete Slack upload with given View ID.
    """
    uploads = _get_slack_uploads()
    result = uploads.delete_one({'view_id': view_id})
    if result.deleted_count != 1:
        raise NotFoundException(
            f"Expected 1 Slack Upload with View ID: {view_id} to be deleted, got {result.deleted_count} deleted")


def vector_search_sections(user_org_domain: str, query_vector_embedding: List[float], query_proper_nouns: List[str], document_limit: int) -> List[VectorSearchSectionResult]:
    """
    Performs vector search to retrieve most relevant sections associated with given query.
    """

    # Construct filters for org domain and proper nouns.
    filters_list: List[Dict] = []
    filters_list.append({
        "org_domain": user_org_domain
    })

    if len(query_proper_nouns) > 0:
        # For now we are ok if any one of the proper nouns in the list is found
        # in a doc. Higher false negatives but hopefully the LLM pipeline can
        # help remove the false negatives.
        filters_list.append({
            "proper_nouns_in_doc": {
                "$in": query_proper_nouns
            }
        })

    sections = _get_sections()
    pipeline = [
        {
            "$vectorSearch": {
                "index": _get_vector_index_name(),
                "path": "summary_vector_embedding",
                "queryVector":  query_vector_embedding,
                # Number must be between document limit and 10000.
                # Documentation recommends ratio of 10 to 20 nearest neighbors for limit of 1 document.
                "numCandidates": int(min(10000, 20*document_limit)),
                "limit": document_limit,
                "filter": {
                    "$and": filters_list

                }
            },
        },
        {
            "$project": {
                '_id': 1,
                'url': 1,
                'text': 1,
                'score': {
                    '$meta': 'vectorSearchScore'
                }
            }
        }
    ]
    results = sections.aggregate(pipeline)

    vss_results: List[VectorSearchSectionResult] = []
    for res in results:
        vss_results.append(VectorSearchSectionResult(**res))
    return vss_results


def insert_api_key(api_key_model: APIKeyModel):
    """
    Insert API key in the database.
    """
    api_keys = _get_api_keys()
    api_key_model.created = _get_current_time()
    api_keys.insert_one(api_key_model.model_dump())


def get_api_key_for_domain(org_domain: str) -> APIKeyModel:
    """
    Fetch API Key for given organization domain.
    """
    api_keys = _get_api_keys()
    api_key_dict = api_keys.find_one({"org_domain": org_domain})
    if not api_key_dict:
        raise NotFoundException(
            f'API key not found for Org domain {org_domain}')
    return APIKeyModel(**api_key_dict)


def get_api_key_from_hashed_value(hashed_key_value: str) -> APIKeyModel:
    """
    Fetch API Key with given ID.
    """
    api_keys = _get_api_keys()
    api_key_dict = api_keys.find_one({"hashed_key_value": hashed_key_value})
    if not api_key_dict:
        raise NotFoundException(
            f'API key not found for hashed value: {hashed_key_value}')
    return APIKeyModel(**api_key_dict)


def delete_api_key_for_domain(org_domain: str) -> APIKeyModel:
    """
    Delete API Key for given organization domain.
    """
    api_keys = _get_api_keys()
    result = api_keys.delete_one({'org_domain': org_domain})
    if result.deleted_count != 1:
        raise NotFoundException(
            f"Expected 1 API key to be deleted, got {result.deleted_count} deleted")


def create_inference_result(if_result_model: InferenceResultModel):
    """
    Creates inference result in the database.
    """
    if_result_model.created = _get_current_time()
    inference_results = _get_inference_results()
    inference_results.insert_one(if_result_model.model_dump(exclude=['id']))


def write_inference_and_chat_messages_transactioanlly(if_result_model: InferenceResultModel,
                                                      chat_message_user_model: ChatMessageModel, chat_message_bot_model: ChatMessageModel):
    """
    Write Inference Result and Chat Messages Transacationally.
    """
    assert chat_message_user_model.creator_type == MessageCreatorType.HUMAN, f"Expected Human creator type in {chat_message_user_model} model"
    assert chat_message_bot_model.creator_type == MessageCreatorType.BOT, f"Expected Bot creator type in {chat_message_bot_model} model"
    client = _get_mongo_client()
    inference_results = _get_inference_results()
    chat_messages = _get_chat_messages()

    created_time = _get_current_time()
    if_result_model.created = created_time
    chat_message_user_model.created = created_time
    chat_message_bot_model.created = created_time
    with client.start_session() as session:
        with session.start_transaction():
            chat_messages.insert_one(
                chat_message_user_model.model_dump(exclude=['id']))
            bot_message_result = chat_messages.insert_one(
                chat_message_bot_model.model_dump(exclude=['id']))

            if_result_model.chat_message_id = str(
                bot_message_result.inserted_id)
            inference_results.insert_one(
                if_result_model.model_dump(exclude=['id']))
