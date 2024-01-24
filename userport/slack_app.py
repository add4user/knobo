import os
import pprint
import json
from enum import Enum
from typing import Dict
from slack_sdk import WebClient
from slack_sdk.web.slack_response import SlackResponse
from dotenv import load_dotenv
from flask import Blueprint, request, jsonify, g
from userport.exceptions import APIException
from pydantic import BaseModel
from userport.slack_modal_views import (
    ViewCreatedResponse,
    CreateDocModalView,
    InteractionPayload,
    SubmissionPayload,
    CreateDocSubmissionPayload,
    CancelPayload
)

bp = Blueprint('slack_app', __name__)

load_dotenv()  # take environment variables from .env.


def get_slack_web_client() -> WebClient:
    if 'slack_web_client' not in g:
        # Create a new client and connect to the server
        g.slack_web_client = WebClient(
            token=os.environ['SLACK_OAUTH_BOT_TOKEN'])

    return g.slack_web_client


def get_json_data_from_request():
    """
    Returns JSON data from request and throws exception if data is not in the correct format.
    """
    try:
        return request.get_json()
    except Exception as e:
        raise APIException(
            status_code=400, message='Request expected to have JSON data but doesn\'t')


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


class SlashCommandRequest(BaseModel):
    """
    Class that validates Slash Command Request.

    Reference: https://api.slack.com/interactivity/slash-commands#app_command_handling
    """
    command: str
    trigger_id: str


class SlashCommandVisibility(Enum):
    PRIVATE = "ephemeral"
    PUBLIC = "in_channel"


def make_slash_command_response(visibility: SlashCommandVisibility, text: str):
    """
    Helper to create response for Slash Command request.
    """
    return {"response_type": visibility.name, "text": text}, 200


@bp.errorhandler(APIException)
def invalid_api_usage(e):
    """
    Handler to convert API exception to JSON response.
    """
    return jsonify(e.to_dict()), e.get_status_code()


@bp.route('/slack/events', methods=['POST'])
def handle_events():
    """
    Single handler to manage all Slack Events (at_mention, message etc.) for Knobo App.
    """
    data = get_json_data_from_request()

    if is_url_verification_request(data):
        # Return challenge field back to verify URL.
        return data['challenge'], 200

    verify_app_id(data)
    pprint.pprint(data)
    return "ok", 200


@bp.route('/slack/slash-command', methods=['POST'])
def handle_slash_command():
    """
    We always want to acknowledge the Slash command per 
    https://api.slack.com/interactivity/slash-commands#responding_with_errors.
    So whenever we encounter a problem, we should just log it and send a response.
    """
    try:
        slash_command_request = SlashCommandRequest(**request.form)
        if slash_command_request.command == '/knobo-create-doc':
            web_client = get_slack_web_client()
            slack_response: SlackResponse = web_client.views_open(
                trigger_id=slash_command_request.trigger_id, view=CreateDocModalView.create_view())

            view_created_response = ViewCreatedResponse(**slack_response.data)
            # TODO: Store view ID in db so we can manage it in the future.
            print("Created view ID: ", view_created_response.get_id())
            return "", 200
    except Exception as e:
        print(
            f"Got error: {e} when handling slash command request: {request.form}")
        return make_slash_command_response(
            visibility=SlashCommandVisibility.PRIVATE, text='Sorry we encountered an internal error and were unable to process your Slash Command')

    print(
        f'Unsupported slash command received: {slash_command_request.command}')
    return make_slash_command_response(visibility=SlashCommandVisibility.PRIVATE,
                                       text=f'Sorry we encountered an unsupported Slash command: {slash_command_request.command} . Please check documentation.')


@bp.route('/slack/interactive-endpoint', methods=['POST'])
def handle_interactive_endpoint():
    interal_error_message = "Sorry encountered an internal error when handling modal input interaction"
    if 'payload' not in request.form:
        print(f'Expected "payload" field in form, got: {request.form}')
        return interal_error_message, 200

    payload_dict: Dict
    try:
        payload_dict = json.loads(request.form['payload'])
    except Exception as e:
        print(
            f"Expected JSON payload in interaction, got errror when parsing: {e}")
        return interal_error_message, 200
    pprint.pprint(payload_dict)

    try:
        payload = InteractionPayload(**payload_dict)
        if payload.is_view_interaction():
            if payload.is_view_closed():
                # TODO: Delete Conversation with given view ID since the view has been closed.
                cancelled_payload = CancelPayload(**payload_dict)
                print("create doc cancelled: ", cancelled_payload)
            elif payload.is_view_submission():
                if SubmissionPayload(**payload_dict).get_title() == CreateDocModalView.get_create_doc_view_title():
                    create_doc_payload = CreateDocSubmissionPayload(
                        **payload_dict)
                    print("Heading markdown: ",
                          create_doc_payload.get_heading_markdown())
                    print("Body markdown: ")
                    print(create_doc_payload.get_body_markdown())
    except Exception as e:
        print(f"Encountered error: {e} when parsing payload: {payload_dict}")
        return interal_error_message, 200

    return "", 200
