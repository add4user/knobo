from flask import Blueprint, render_template, request, session, jsonify
from flask_login import login_required
from userport.index.page_section_manager import PageSectionManager
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


@bp.route('/api/v1/upload_url', methods=['POST'])
@login_required
def upload_url():
    """
    URL uploaded by user. The API dispatches upload work to the background (via Celery)
    and returns an upload ID to the client.
    """
    user_id = get_user_id()
    data = request.get_json()
    if 'url' not in data:
        raise APIException(status_code=400, message='Missing URL in request')

    url = data['url']
    background_upload_url.delay(user_id, url)
    return {}, 200


@shared_task()
def background_upload_url(user_id: str, url: str):
    """
    Celery task to index page associated with given URL.
    """
    psm = PageSectionManager()
    psm.fetch(url)
