from flask import Blueprint, render_template, request, session, jsonify
from flask_login import login_required
from userport.index import PageSection, PageSectionManager
from userport.models import (
    UploadStatus,
    UploadModel,
    UserModel,
    APIKeyModel,
    InferenceResultModel,
    UserFeedback,
    ChatMessageModel,
    MessageCreatorType
)
from userport.inference_assistant import InferenceAssistant, InferenceResult
from userport.utils import generate_hash
from typing import List
from userport.db import (
    insert_page_sections_transactionally,
    create_upload,
    update_upload_status,
    get_upload_by_id,
    get_user_by_id,
    list_uploads_by_org_domain,
    delete_upload_and_sections_transactionally,
    upload_already_has_sections,
    insert_api_key,
    get_api_key_for_domain,
    get_api_key_from_hashed_value,
    delete_api_key_for_domain,
    create_inference_result,
    write_inference_and_chat_messages_transactioanlly,
    NotFoundException
)
from celery import shared_task
import secrets

bp = Blueprint('application', __name__)

# Set to false when not debugging.
debug = False


class APIException(Exception):
    """
    Class to convert API errors to JSON messages with appropriate formats.
    """

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__()
        self.status_code = status_code
        self.message = message

    def to_dict(self):
        return {'error_code': self.status_code, 'message': self.message}

    def get_status_code(self):
        return self.status_code


@bp.errorhandler(APIException)
def invalid_api_usage(e):
    """
    Handler to convert API exception to JSON response.
    """
    return jsonify(e.to_dict()), e.get_status_code()


# Used only when user is already logged in.
def get_user_id():
    return session["_user_id"]


"""
Upload URL views and APIs.
"""


@bp.route('/', methods=['GET'])
@login_required
def uploads_view():
    """
    View to show upload URLs by the user (if any).
    """
    return render_template('application/uploads.html')


@bp.route('/api/v1/urls', methods=['GET'])
@login_required
def handle_urls():
    """
    Fetch list of URLs uploaded for the user's organization domain.
    """
    user_id = get_user_id()

    user: UserModel
    try:
        user = get_user_by_id(user_id)
    except NotFoundException as e:
        print(e)
        raise APIException(
            status_code=404, message=f"User with id {user_id} not found")
    except Exception as e:
        print(e)
        raise APIException(
            status_code=500, message=f"Internal error! Failed to user with id {user_id}")

    upload_model_list: List[UploadModel] = []
    org_domain = user.org_domain
    try:
        upload_model_list = list_uploads_by_org_domain(org_domain=org_domain)
    except Exception as e:
        print(e)
        raise APIException(
            status_code=500, message=f"Internal Error! failed to list uploads for domain {org_domain}")

    return {"uploads": [upload_model.model_dump()
                        for upload_model in upload_model_list]}, 200


@bp.route('/api/v1/url', methods=['POST', 'GET', 'DELETE'])
@login_required
def handle_url():
    """
    POST:
    URL uploaded by user. The API dispatches upload work to the background (via Celery)
    and returns an upload ID to the client.

    GET:
    Fetch uploaded URL using given upload ID.

    DELETE:
    Delete URL with given upload ID.
    """
    if request.method == 'POST':
        user_id = get_user_id()
        try:
            data = request.get_json()
        except Exception as e:
            raise APIException(
                status_code=400, message='Request expected to have JSON data but doesn\'t')

        if 'url' not in data:
            raise APIException(
                status_code=400, message='Missing URL in request')

        url = data['url']
        upload_id: str
        try:
            upload_id = create_upload(user_id=user_id, url=url)
        except Exception as e:
            print(e)
            raise APIException(
                status_code=500, message=f"Internal error! Failed to upload URL: {url}")

        upload_model: UploadModel
        try:
            upload_model = get_upload_by_id(upload_id)
        except Exception as e:
            print(e)
            raise APIException(
                status_code=500, message=f"Internal error! Failed to fetch model with Id: {upload_id}")

        if debug:
            # Return early without starting background task.
            return upload_model.model_dump(), 200

        try:
            background_upload_url.delay(user_id, url, upload_id)
        except Exception as e:
            print(e)
            raise APIException(status_code=500,
                               message=f"Internal error! Failed to initiate upload for URL: {url}")
        return upload_model.model_dump(), 200
    elif request.method == 'GET':
        # Fetch upload status.
        upload_id = request.args.get('id', '')
        if upload_id == '':
            raise APIException(
                status_code=400, message='Missing ID in upload request')

        upload_model: UploadModel
        try:
            upload_model = get_upload_by_id(upload_id)
        except Exception as e:
            print(e)
            raise APIException(
                status_code=500, message=f'Internal error! Failed to get upload status for id: {upload_id}')

        got_model_dict = upload_model.model_dump()
        if debug:
            update_upload_status(upload_id=upload_id,
                                 upload_status=UploadStatus.COMPLETE)
        return got_model_dict, 200
    else:
        # Delete uploaded URL.
        upload_id = request.args.get('id', '')
        if upload_id == '':
            raise APIException(
                status_code=400, message='Missing ID in upload request')

        try:
            delete_upload_and_sections_transactionally(upload_id)
        except Exception as e:
            print(e)
            raise APIException(
                status_code=500, message=f"Internal error! Could not delete upload with ID: {upload_id}")

        return {}, 200


# Upload URL via Celery task. Retries with 5 second delay up to 3 times in case of exception.
@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def background_upload_url(self, user_id: str, url: str, upload_id: str):
    """
    Celery task to index page associated with given URL.
    """
    if not upload_already_has_sections(upload_id):
        psm = PageSectionManager()
        print("Fetching page sections....")
        try:
            root_page_section: PageSection = psm.fetch(url)
        except Exception as e:
            print(e)
            try:
                update_upload_status(upload_id=upload_id,
                                     upload_status=UploadStatus.FAILED, error_message=str(e))
            except Exception as err:
                print(err)
                raise err
            raise e
        print("Beginning write to database...")
        try:
            insert_page_sections_transactionally(
                user_id=user_id, url=url, upload_id=upload_id, root_page_section=root_page_section)
        except Exception as e:
            print(e)
            try:
                update_upload_status(upload_id=upload_id,
                                     upload_status=UploadStatus.FAILED, error_message=str(e))
            except Exception as err:
                print(err)
                raise err
            raise e
    else:
        print("Upload already has sections")

    print("Done with writing sections collection")
    try:
        update_upload_status(upload_id=upload_id,
                             upload_status=UploadStatus.COMPLETE)
    except Exception as e:
        print(e)
        raise e


"""
API key views and APIs.
"""


@bp.route('/api-key', methods=['GET'])
@login_required
def api_key_view():
    """
    View to allow creation and display of API key.
    """
    return render_template('application/api_key.html')


@bp.route('/api/v1/api-key', methods=['POST', 'GET', 'DELETE'])
@login_required
def handle_api_key():
    """
    View to allow creation and display of API key.
    """
    user_id = get_user_id()
    user: UserModel
    try:
        user = get_user_by_id(user_id)
    except Exception as e:
        print(e)
        raise APIException(
            status_code=500, message=f'User with id {user_id} does not exist')

    if request.method == 'POST':
        # Check if key already exists.
        try:
            get_api_key_for_domain(org_domain=user.org_domain)
            raise APIException(
                status_code=409, message=f'API key already exists in org {user.org_domain}')
        except NotFoundException as e:
            # Do nothing since this is expected.
            pass
        except Exception as e:
            print(e)
            raise APIException(
                status_code=500, message=f'Server error when trying to fetch API key for domain: {user.org_domain}')

        # Generate new key.
        key_value: str = secrets.token_urlsafe(16)
        hashed_key_value: str = generate_hash(key_value)
        api_key_model = APIKeyModel(
            key_prefix=key_value[:5], hashed_key_value=hashed_key_value, org_domain=user.org_domain, creator_id=user_id)
        try:
            insert_api_key(api_key_model)
        except Exception as e:
            print(e)
            raise APIException(
                status_code=500, message=f"Failed to create API key for user {user_id}")

        return {"key": api_key_model.model_dump(), "raw_value": key_value}, 200
    elif request.method == 'GET':
        api_key_model: APIKeyModel
        try:
            api_key_model = get_api_key_for_domain(org_domain=user.org_domain)
        except NotFoundException as e:
            # Return empty key.
            return {"key": ""}, 200
        except Exception as e:
            print(e)
            raise APIException(
                status_code=500, message=f'Ran into error fetching API key for domain {user.org_domain}')

        return {"key": api_key_model.model_dump()}, 200
    elif request.method == 'DELETE':
        try:
            delete_api_key_for_domain(org_domain=user.org_domain)
        except NotFoundException as e:
            raise APIException(status_code=404, message=str(e))
        except Exception as e:
            print(e)
            raise APIException(
                status_code=500, message=f'Failed to delete API key for domain {user.org_domain}')

        return {}, 200


"""
Inference APIs.
"""


@bp.route('/api/v1/inference', methods=['POST'])
@login_required
def perform_inference():
    user_id = get_user_id()
    user: UserModel
    try:
        user = get_user_by_id(user_id)
    except Exception as e:
        print(e)
        raise APIException(
            status_code=500, message=f'User with id {user_id} does not exist')
    org_domain: str = user.org_domain

    if 'X-API-KEY' not in request.headers:
        raise APIException(
            status_code=400, message='Missing Authentication Credentials')

    # Authenticate request.
    api_key: str = request.headers['X-API-KEY']
    try:
        api_key_model: APIKeyModel = get_api_key_from_hashed_value(
            hashed_key_value=generate_hash(api_key))
        if api_key_model.org_domain != org_domain:
            raise NotFoundException(
                f'User org {org_domain} does not match API key org: {api_key_model.org_domain}')
    except NotFoundException as e:
        print(e)
        raise APIException(
            status_code=403, message='Invalid Authentication credentials')
    except Exception as e:
        print(e)
        raise APIException(
            status_code=500, message="Failed to post a chat message")

    # Get data from request body.
    try:
        data = request.get_json()
    except Exception as e:
        raise APIException(
            status_code=400, message='Chat request expected to have JSON data but doesn\'t')

    if 'user_query' not in data:
        raise APIException(
            status_code=400, message='Missing query in Chat request')
    user_query = data['user_query']

    # Run inference.
    if_assistant = InferenceAssistant()
    if_result: InferenceResult = if_assistant.answer(
        user_org_domain=org_domain, user_query=user_query)

    if debug:
        print("exception if any: ", if_result.exception_message)
        for section in if_result.relevant_sections:
            print("section text: ", section.text[:50])
            print("section score: ", section.score)
            print("\n")

        print("proper nouns in query")
        print(if_result.user_query_proper_nouns)

        print("\nFinal answer\n")
        print(if_result.answer_text)

        print("\nFinal section number")
        print(if_result.chosen_section_text[:50])
        print("\n")

        print("Latency: " + str(if_result.inference_latency) + " ms")

    # Create model to write to db.
    if_result_model = InferenceResultModel(
        org_domain=org_domain,
        user_query=if_result.user_query,
        user_query_vector_embedding=if_result.user_query_vector_embedding,
        user_query_proper_nouns=if_result.user_query_proper_nouns,
        document_limit=if_result.document_limit,
        relevant_sections=if_result.relevant_sections,
        final_text_prompt=if_result.final_text_prompt,
        information_found=if_result.information_found,
        chosen_section_text=if_result.chosen_section_text,
        answer_text=if_result.answer_text,
        user_feedback=UserFeedback(),
        inference_latency=if_result.inference_latency,
        exception_message=if_result.exception_message,
    )

    if if_result.exception_message:
        # Inference failed, store the inference result in db and throw an exception.
        print(if_result.exception_message)
        try:
            create_inference_result(if_result_model)
        except Exception as e:
            print(e)
        raise APIException(
            status_code=500, message="Internal Server error when fetching chat response")

    # Create ChatMessage models to write to db.
    chat_message_user_model = ChatMessageModel(
        org_domain=org_domain, human_user_id=user_id, text=user_query,
        creator_id=user_id, creator_type=MessageCreatorType.HUMAN
    )
    chat_message_bot_model = ChatMessageModel(
        org_domain=org_domain, human_user_id=user_id, text=if_result.answer_text,
        creator_id=if_result.bot_id, creator_type=MessageCreatorType.BOT
    )

    try:
        write_inference_and_chat_messages_transactioanlly(if_result_model=if_result_model,
                                                          chat_message_user_model=chat_message_user_model, chat_message_bot_model=chat_message_bot_model)
    except Exception as e:
        print(e)
        raise APIException(
            status_code=500, message="Failed to write Chat message")

    return chat_message_bot_model.model_dump(), 200
