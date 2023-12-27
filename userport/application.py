from flask import Blueprint, render_template, request, session, jsonify
from flask_login import login_required
from userport.index import PageSection, PageSectionManager
from userport.models import UploadStatus
from userport.db import insert_page_sections_transactionally, create_upload, update_upload_status, get_upload_status
from celery import shared_task

bp = Blueprint('application', __name__)


class APIException(Exception):
    """
    Class to convert API errors to JSON messages with appropriate formats.
    """

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__()
        self.status_code = status_code
        self.message = message

    def to_dict(self):
        return {'status_code': self.status_code, 'message': self.message}

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
    View to show upload URL options.
    """
    return render_template('application/uploads.html')


@bp.route('/api/v1/upload_url', methods=['GET', 'POST'])
@login_required
def upload_url():
    """
    POST:
    URL uploaded by user. The API dispatches upload work to the background (via Celery)
    and returns an upload ID to the client.

    GET:
    Fetch upload status for given upload ID.
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

        try:
            background_upload_url.delay(user_id, url, upload_id)
        except Exception as e:
            print(e)
            raise APIException(status_code=500,
                               message=f"Internal error! Failed to initiate upload for URL: {url}")
        return {"upload_id": upload_id}, 200
    else:
        # Fetch upload status.
        upload_id = request.args.get('id', '')
        if upload_id == '':
            raise APIException(
                status_code=400, message='Missing ID in upload request')

        upload_status: UploadStatus
        try:
            upload_status = get_upload_status(upload_id)
        except Exception as e:
            print(e)
            raise APIException(
                status_code=500, message=f'Internal error! Failed to get upload status for id: {upload_id}')

        return {'id': upload_id, 'upload_status': upload_status}, 200


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
