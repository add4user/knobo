import os
import pprint
from dotenv import load_dotenv
from flask import Blueprint, request, jsonify
from userport.exceptions import APIException

bp = Blueprint('slack_app', __name__)

load_dotenv()  # take environment variables from .env.


@bp.errorhandler(APIException)
def invalid_api_usage(e):
    """
    Handler to convert API exception to JSON response.
    """
    return jsonify(e.to_dict()), e.get_status_code()


@bp.route('/slack/events', methods=['POST'])
def handle_slack_app_events():
    """
    Single handler to manage all Slack Events for Knobo App.
    """
    data = None
    try:
        data = request.get_json()
    except Exception as e:
        raise APIException(
            status_code=400, message='Request expected to have JSON data but doesn\'t')

    if is_url_verification_request(data):
        # Return challenge field back to verify URL.
        return data['challenge'], 200

    verify_app_id(data)
    pprint.pprint(data)
    return "ok", 200


def is_url_verification_request(data):
    return 'type' in data and data['type'] == 'url_verification'


def verify_app_id(data):
    """
    Verify App ID in Event payload matches known Knobo App ID.
    """
    if 'api_app_id' not in data:
        raise APIException(
            status_code=400, message="App Id not present, invalid request")
    if os.environ.get("SLACK_API_APP_ID") != data['api_app_id']:
        raise APIException(
            status_code=403, message=f"Invalid App Id {data['api_app_id']}")
