import os
import pprint
import json
import logging
from enum import Enum
from typing import Dict, ClassVar, Optional, List
from slack_sdk import WebClient
from slack_sdk.webhook import WebhookClient
from slack_sdk.web.slack_response import SlackResponse
from dotenv import load_dotenv
from flask import Blueprint, request, jsonify, g
from userport.exceptions import APIException
from pydantic import BaseModel, validator
from userport.slack_page_indexer import SlackPageIndexer
from userport.slack_inference import SlackInference
from userport.slack_blocks import RichTextBlock
from userport.slack_modal_views import (
    ViewCreatedResponse,
    CreateDocModalView,
    InteractionPayload,
    SubmissionPayload,
    CreateDocSubmissionPayload,
    CancelPayload,
    MessageShortcutPayload,
    PlaceDocModalView,
    create_document_view,
    place_document_view,
    place_document_with_new_page_title_input,
    place_document_with_selected_page_option,
    BlockActionsPayload,
    SelectMenuBlockActionsPayload,
    PlaceDocSubmissionPayload,
    PlaceDocNewPageSubmissionPayload
)
from userport.markdown_parser import MarkdownToRichTextConverter
from userport.slack_models import (
    SlackUpload,
    SlackUploadStatus,
    SlackSection
)
from userport.utils import convert_to_markdown_heading
import userport.db
from celery import shared_task

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


class EventRequest(BaseModel):
    """
    Class that validates Events API Request.

    Reference: https://api.slack.com/apis/connections/events-api#event-type-structure.
    """
    MESSAGE_TYPE: ClassVar[str] = 'message'

    class Event(BaseModel):
        type: str
        subtype: Optional[str] = None
        channel: str

    event: Event

    def is_message_created_event(self) -> bool:
        """
        Return True if message created event else False.
        """
        return self.event.type == EventRequest.MESSAGE_TYPE and self.event.subtype == None


class IMMessageCreatedEventRequest(BaseModel):
    """
    Class that validates Events API Message Request.

    Reference: https://api.slack.com/events/message.
    """
    MESSAGE_TYPE: ClassVar[str] = 'message'
    IM_CHANNEL_TYPE: ClassVar[str] = 'im'

    class Event(BaseModel):
        type: str
        team: str
        user: str
        channel: str
        channel_type: str
        blocks: List[RichTextBlock]

        @validator("type")
        def validate_type(cls, v):
            if v != IMMessageCreatedEventRequest.MESSAGE_TYPE:
                raise ValueError(
                    f"Expected {IMMessageCreatedEventRequest.MESSAGE_TYPE} as type, got {v}")
            return v

        @validator("channel_type")
        def validate_channel_type(cls, v):
            if v != IMMessageCreatedEventRequest.IM_CHANNEL_TYPE:
                raise ValueError(
                    f"Expected {IMMessageCreatedEventRequest.IM_CHANNEL_TYPE} as channel type, got {v}")
            return v

    event: Event

    def get_markdown_text(self) -> str:
        """
        Get message as markdown formatted text.
        """
        assert len(
            self.event.blocks) == 1, f"Expected 1 text block in message, got {self.event.blocks}"
        return self.event.blocks[0].get_markdown()

    def get_team_id(self) -> str:
        """
        Return team ID of the given event request.
        """
        return self.event.team

    def get_user_id(self) -> str:
        """
        Return user ID of the given event request.
        """
        return self.event.user

    def get_channel_id(self) -> str:
        """
        Return channel ID of the event given requeest.
        """
        return self.event.channel


class SlashCommandRequest(BaseModel):
    """
    Class that validates Slash Command Request.

    Reference: https://api.slack.com/interactivity/slash-commands#app_command_handling
    """
    command: str
    trigger_id: str
    response_url: str
    team_id: str
    user_id: str
    text: str
    channel_id: str


class SlashCommandVisibility(Enum):
    PRIVATE = "ephemeral"
    PUBLIC = "in_channel"


class ViewUpdateResponse(BaseModel):
    """
    Class to update View as HTTP response.

    Rererence: https://api.slack.com/surfaces/modals#updating_response
    """
    ACTION_VALUE: ClassVar[str] = "update"

    response_action: str = ACTION_VALUE
    view: PlaceDocModalView

    @validator("response_action")
    def validate_type(cls, v):
        if v != ViewUpdateResponse.ACTION_VALUE:
            raise ValueError(
                f"Expected {ViewUpdateResponse.ACTION_VALUE} as response_action value, got {v}")
        return v


class UserInfoResponse(BaseModel):
    """
    Class with response from Slack User Info request.s

    Reference: https://api.slack.com/methods/users.info#examples
    """
    class UserObject(BaseModel):
        class UserProfile(BaseModel):
            email: str
        profile: UserProfile
    user: UserObject

    def get_email(self) -> str:
        """
        Return user's email.
        """
        return self.user.profile.email


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

    try:
        event_request = EventRequest(**data)
        if event_request.is_message_created_event():
            message_event_request = IMMessageCreatedEventRequest(**data)

            user_query: str = message_event_request.get_markdown_text()
            team_id: str = message_event_request.get_team_id()
            channel_id: str = message_event_request.get_channel_id()
            user_id: str = message_event_request.get_user_id()
            # Since this is already an IM message, we can generate a public response.
            private_visibility: bool = False

            answer_user_query_in_background.delay(
                user_query, team_id, channel_id, user_id, private_visibility)
    except Exception as e:
        print(f"Got error: {e} when handling slash command request: {data}")

    return "", 200


@bp.route('/slack/slash-command', methods=['POST'])
def handle_slash_command():
    """
    We always want to acknowledge the Slash command per 
    https://api.slack.com/interactivity/slash-commands#responding_with_errors.
    So whenever we encounter a problem, we should just log it and send a response.

    We have 3 seconds to respond per https://api.slack.com/interactivity/slash-commands#responding_basic_receipt.
    """
    # Uncomment for debugging.
    # pprint.pprint(request.form)

    try:
        slash_command_request = SlashCommandRequest(**request.form)
        if slash_command_request.command == '/knobo-ask':
            user_query: str = slash_command_request.text
            if len(user_query) == 0:
                return "You forgot to ask a question after the command. Please try again!", 200
            team_id: str = slash_command_request.team_id
            channel_id: str = slash_command_request.channel_id
            user_id: str = slash_command_request.user_id
            # We need to call conversations.info to know type of channel
            # https://api.slack.com/methods/conversations.info to decide
            # if visibility is private or public.
            private_visibility: bool = True

            answer_user_query_in_background.delay(
                user_query, team_id, channel_id, user_id, private_visibility)
            return f"{user_query}\n\nAnswering...please wait.", 200
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
    """
    Handle View closed and View submission payloads.

    We have 3 seconds to respond: https://api.slack.com/interactivity/handling#acknowledgment_response
    """
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

    # Uncomment whenever you need to find out new fields to use from the payload.
    # pprint.pprint(payload_dict)

    try:
        payload = InteractionPayload(**payload_dict)
        if payload.is_message_shortcut():
            # Handle Shortcut message.
            shortcut_payload = MessageShortcutPayload(**payload_dict)
            if shortcut_payload.is_create_doc_shortcut():
                # User wants to add a section to the documentation.
                create_modal_from_shortcut_in_background.delay(
                    shortcut_payload.model_dump_json())
        elif payload.is_view_interaction():
            # Handle Modal View closing or submission.
            if payload.is_view_closed():
                # User has closed the view.
                cancel_payload = CancelPayload(**payload_dict)
                view_id = cancel_payload.get_view_id()

                delete_upload_in_background.delay(view_id)

            elif payload.is_view_submission():
                # User has submitted the view.
                submission_payload = SubmissionPayload(**payload_dict)
                if submission_payload.get_view_title() == CreateDocModalView.get_view_title():
                    # The view submitted is the Create Section view.
                    create_doc_payload = CreateDocSubmissionPayload(
                        **payload_dict)
                    view_id = create_doc_payload.get_view_id()
                    heading = create_doc_payload.get_heading_plain_text()
                    body = create_doc_payload.get_body_markdown()

                    update_upload_in_background.delay(
                        view_id, heading, body)

                    # Return an updated view asking user where to place the added section.
                    view_update_response = ViewUpdateResponse(
                        view=place_document_view())
                    return view_update_response.model_dump(exclude_none=True), 200
                elif submission_payload.get_view_title() == PlaceDocModalView.get_view_title():
                    if PlaceDocSubmissionPayload(**payload_dict).is_new_page_submission():
                        new_page_submission_payload = PlaceDocNewPageSubmissionPayload(
                            **payload_dict)

                        new_page_title = new_page_submission_payload.get_new_page_title()
                        view_id = new_page_submission_payload.get_view_id()
                        create_new_page_in_background.delay(
                            view_id=view_id, new_page_title=new_page_title)

        elif payload.is_block_actions():
            # Handle Block Elements related updates within a view.
            if BlockActionsPayload(**payload_dict).is_page_selection_action_id():
                # User has selected a Page to the add new section to.
                select_menu_actions_payload = SelectMenuBlockActionsPayload(
                    **payload_dict)
                if len(select_menu_actions_payload.actions) != 1:
                    raise ValueError(
                        f"Expected 1 action in payload, got {select_menu_actions_payload} instead")

                selected_menu_action = select_menu_actions_payload.actions[0]
                if PlaceDocModalView.is_create_new_page_action(selected_menu_action):
                    # Return an updated view asking user for new page title input.
                    update_view_with_new_page_title_in_background.delay(
                        select_menu_actions_payload.model_dump_json(exclude_none=True))
                else:
                    # Return updated view with just menu options.
                    # TODO: Make this a view dependent on the selected option here.
                    update_view_with_place_document_selected_page_in_background.delay(
                        select_menu_actions_payload.model_dump_json(exclude_none=True))

    except Exception as e:
        print(f"Encountered error: {e} when parsing payload: {payload_dict}")
        return interal_error_message, 200

    return "", 200


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def answer_user_query_in_background(user_query: str, team_id: str, channel_id: str, user_id: str, private_visibility: bool):
    slack_inference = SlackInference()
    inference_answer: str = slack_inference.answer(
        user_query=user_query, team_id=team_id)

    # Convert to Slack RichTextBlock.
    answer_rich_text_block: RichTextBlock = MarkdownToRichTextConverter().convert(
        markdown_text=inference_answer)

    # Post answer to user as a chat message.
    web_client = get_slack_web_client()
    if private_visibility:
        # Post ephemeral message.
        web_client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            blocks=[
                answer_rich_text_block.model_dump(exclude_none=True)
            ]
        )
    else:
        # Post public message.
        # User user_id as channel argument for IMs per: https://api.slack.com/methods/chat.postMessage#app_home
        # TODO: Change this once we can post public messages in channels as well (in addtion to just IMs)
        web_client.chat_postMessage(
            channel=user_id,
            blocks=[
                answer_rich_text_block.model_dump(exclude_none=True)
            ]
        )


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def create_modal_from_shortcut_in_background(create_doc_shortcut_json: str):
    """
    Create Modal View in shared task and write Slack upload to db after user initiates 
    documentation creation from Shortcut.

    We do this in Celery task since it can take > 3s in API path and
    result in user seeing an operation_timeout error message in the Slack channel.
    """
    create_doc_shortcut = MessageShortcutPayload(
        **json.loads(create_doc_shortcut_json))

    # Create view.
    initial_rich_text_block = create_doc_shortcut.get_rich_text_block()
    view = create_document_view(initial_body_value=initial_rich_text_block)
    web_client = get_slack_web_client()
    slack_response: SlackResponse = web_client.views_open(
        trigger_id=create_doc_shortcut.get_trigger_id(), view=view.model_dump(exclude_none=True))
    view_response = ViewCreatedResponse(**slack_response.data)

    # Write upload to db.
    user_id = create_doc_shortcut.get_user_id()
    team_id = create_doc_shortcut.get_team_id()
    shortcut_callback_id = create_doc_shortcut.get_callback_id()
    response_url = create_doc_shortcut.get_response_url()
    channel_id = create_doc_shortcut.get_channel_id()
    message_ts = create_doc_shortcut.get_message_ts()
    view_id = view_response.get_id()
    userport.db.create_slack_upload(creator_id=user_id, team_id=team_id, view_id=view_id,
                                    response_url=response_url, shortcut_callback_id=shortcut_callback_id,
                                    channel_id=channel_id, message_ts=message_ts)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def delete_upload_in_background(view_id: str):
    """
    Delete Upload with given View ID in background.

    Performed in Celery task so API call path can complete in less than 3s.
    """
    userport.db.delete_slack_upload(view_id=view_id)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def update_upload_in_background(view_id: str, heading: str, text: str):
    """
    Update Upload with heading and body text in the background.

    Performed in Celery task so API call path can complete in less than 3s.
    """
    userport.db.update_slack_upload_text(
        view_id=view_id, heading=heading, text=text)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def update_view_with_new_page_title_in_background(select_menu_block_actions_payload_json: str):
    """
    Update View asking user New page Title input in the background.

    Performed in Celery task so API call path can complete in less than 3s.
    """
    select_menu_block_actions_payload = SelectMenuBlockActionsPayload(
        **json.loads(select_menu_block_actions_payload_json))
    web_client = get_slack_web_client()
    web_client.views_update(
        view_id=select_menu_block_actions_payload.get_view_id(),
        hash=select_menu_block_actions_payload.get_view_hash(),
        view=place_document_with_new_page_title_input().model_dump(exclude_none=True),
    )


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def update_view_with_place_document_selected_page_in_background(select_menu_block_actions_payload_json: str):
    """
    Update View showing user place document view with selected page.

    Performed in Celery task so API call path can complete in less than 3s.
    """
    select_menu_block_actions_payload = SelectMenuBlockActionsPayload(
        **json.loads(select_menu_block_actions_payload_json))
    web_client = get_slack_web_client()
    web_client.views_update(
        view_id=select_menu_block_actions_payload.get_view_id(),
        hash=select_menu_block_actions_payload.get_view_hash(),
        view=place_document_with_selected_page_option().model_dump(exclude_none=True),
    )


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def create_new_page_in_background(view_id: str, new_page_title: str):
    """
    Create New page and complete upload of the section in the background.
    """
    slack_upload: SlackUpload
    try:
        slack_upload = userport.db.get_slack_upload_from_view_id(
            view_id=view_id)
    except userport.db.NotFoundException as e:
        logging.error(
            f"New page creation failed for View ID: {view_id} with error: {e}")
        return

    # Gather information from upload.
    upload_id: str = slack_upload.id
    team_id: str = slack_upload.team_id
    creator_id: str = slack_upload.creator_id
    section_heading_plain_text: str = slack_upload.heading_plain_text
    section_text_markdown: str = slack_upload.text_markdown

    # Get creator email.
    web_client = get_slack_web_client()
    slack_response: SlackResponse = web_client.users_info(user=creator_id)
    creator_email: str = UserInfoResponse(
        **slack_response.data).get_email()

    # Create Slack Section for both section and page.
    page_section = SlackSection(
        upload_id=upload_id,
        team_id=team_id,
        creator_id=creator_id,
        creator_email=creator_email,
        updater_id=creator_id,
        updater_email=creator_email,
        heading=convert_to_markdown_heading(text=new_page_title, number=1)
    )
    child_section = SlackSection(
        upload_id=upload_id,
        team_id=team_id,
        creator_id=creator_id,
        creator_email=creator_email,
        updater_id=creator_id,
        updater_email=creator_email,
        heading=convert_to_markdown_heading(
            text=section_heading_plain_text, number=2),
        text=section_text_markdown
    )

    # Write sections to database.
    page_id, child_id = userport.db.create_slack_page_and_section(
        page_section=page_section, child_section=child_section)

    # Complete upload in background.
    complete_new_page_upload_in_background.delay(upload_id, page_id)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def complete_new_page_upload_in_background(upload_id: str, page_id: str):
    """
    Complete upload process so that the page and child sections can be indexed for retrieval.

    Performed in Celery task so API call path can complete in less than 3s.
    """

    slack_upload: SlackUpload
    try:
        slack_upload = userport.db.get_slack_upload_from_id(
            upload_id=upload_id)
    except userport.db.NotFoundException as e:
        logging.error(
            f"Upload complete failed for Upload ID: {upload_id} with error: {e}")
        return

    webhook = WebhookClient(slack_upload.response_url)
    if slack_upload.status != SlackUploadStatus.IN_PROGRESS:
        # Send Webhook message since upload has started.
        webhook.send(text="Documentation creation is in progress! I will ping you once it's done!",
                     response_type=SlashCommandVisibility.PRIVATE.value)

        userport.db.update_slack_upload_status(
            upload_id=upload_id, upload_status=SlackUploadStatus.IN_PROGRESS)
        logging.info("Updated Upload Status to in progress successfully")

    if slack_upload.status != SlackUploadStatus.COMPLETED:
        # Index the page and associated section.
        indexer = SlackPageIndexer()
        indexer.run(page_id=page_id)

        userport.db.update_slack_upload_status(
            upload_id=upload_id, upload_status=SlackUploadStatus.COMPLETED)
        logging.info("Updated Upload Status to in Completed successfully")

    webhook.send(text="Documentation upload complete!",
                 response_type=SlashCommandVisibility.PRIVATE.value)
