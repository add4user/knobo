from flask import Blueprint, render_template, request, session, jsonify
from flask_login import login_required
from userport.index import PageSection, PageSectionManager
from userport.models import UploadStatus, UploadModel, UserModel
from typing import List, Dict
from userport.db import (
    insert_page_sections_transactionally,
    create_upload,
    update_upload_status,
    get_upload_by_id,
    get_user_by_id,
    list_uploads_by_org_domain,
    delete_upload_with_id,
    NotFoundException
)
from celery import shared_task

bp = Blueprint('application', __name__)

# Remove when not debugging.
debug = True


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


@bp.route('/', methods=['GET'])
@login_required
def uploads_view():
    """
    View to show upload URLs by the user (if any).
    """
    return render_template('application/uploads.html')


@bp.route('/api/v1/list_urls', methods=['GET'])
@login_required
def list_urls():
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
            status_code=400, message=f"User with id {user_id} not found")
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


@bp.route('/api/v1/upload_url', methods=['GET', 'POST'])
@login_required
def upload_url():
    """
    POST:
    URL uploaded by user. The API dispatches upload work to the background (via Celery)
    and returns an upload ID to the client.

    GET:
    Fetch uploaded URL using given upload ID.
    """
    if request.method == 'POST':
        user_id = get_user_id()
        data = request.get_json()
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
    else:
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

        return upload_model.model_dump(), 200


@shared_task()
def background_upload_url(user_id: str, url: str, upload_id: str):
    """
    Celery task to index page associated with given URL.
    """
    psm = PageSectionManager()
    print("Fetching page sections....")
    try:
        root_page_section: PageSection = psm.fetch(url)
    except Exception as e:
        update_upload_status(upload_id=upload_id,
                             upload_status=UploadStatus.FAILED, error_message=str(e))
    print("Beginning write to database...")
    try:
        insert_page_sections_transactionally(
            user_id=user_id, url=url, upload_id=upload_id, root_page_section=root_page_section)
    except Exception as e:
        update_upload_status(upload_id=upload_id,
                             upload_status=UploadStatus.FAILED, error_message=str(e))

    print("Done with writing sections collection")
    update_upload_status(upload_id=upload_id,
                         upload_status=UploadStatus.COMPLETE)


@bp.route('/api/v1/delete_url', methods=['GET'])
@login_required
def delete_url():
    """
    Delete URL with given upload ID.
    """
    upload_id = request.args.get('id', '')
    if upload_id == '':
        raise APIException(
            status_code=400, message='Missing ID in upload request')

    try:
        delete_upload_with_id(upload_id)
    except NotFoundException as e:
        print(e)
        raise APIException(
            status_code=400, message=f"Did not find upload with ID: {upload_id}")
    except Exception as e:
        print(e)
        raise APIException(
            status_code=500, message=f"Internal error! Could not delete upload with ID: {upload_id}")

    return {}, 200
