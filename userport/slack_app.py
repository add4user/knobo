from markupsafe import escape
import os
import pprint
import json
import logging
from enum import Enum
from typing import Dict, ClassVar, Optional, List
from slack_sdk import WebClient
from slack_sdk.web.slack_response import SlackResponse
from dotenv import load_dotenv
from flask import Blueprint, request, jsonify, g
from userport.exceptions import APIException
from pydantic import BaseModel, validator
from userport.slack_page_indexer import SlackPageIndexer
from userport.slack_inference import SlackInference
from userport.slack_blocks import MessageBlock, RichTextBlock
from userport.slack_modal_views import (
    ViewCreatedResponse,
    InteractionPayload,
    SubmissionPayload,
    CreateDocSubmissionPayload,
    CancelPayload,
    MessageShortcutPayload,
    BaseModalView,
    BlockActionsPayload,
    SelectMenuBlockActionsPayload,
    PlaceDocSubmissionPayload,
    PlaceDocNewPageSubmissionPayload,
    CreateDocViewFactory,
    PlaceDocViewFactory,
    PlaceDocSelectParentOrPositionState,
    GlobalShortcutPayload,
    EditDocViewFactory,
    EditDocBlockAction,
    CommonShortcutPayload
)
from bson.objectid import ObjectId
from userport.slack_html_gen import SlackHTMLGenerator
from userport.slack_models import (
    SlackUpload,
    SlackUploadStatus,
    SlackSection,
    FindSlackSectionRequest,
    UpdateSlackSectionRequest,
    FindAndUpateSlackSectionRequest,
)
import userport.utils
import userport.db
from celery import shared_task

bp = Blueprint('slack_app', __name__)

load_dotenv()  # take environment variables from .env.

# TODO: Change to custom domain in production.
HARDCODED_HOSTNAME = 'https://fb5e-2409-40f2-1041-7619-857c-13e-96b0-e84d.ngrok-free.app'


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

    class Authorization(BaseModel):
        is_bot: bool
        user_id: str

        @validator("is_bot")
        def validate_is_bot(cls, v):
            if not v:
                raise ValueError(
                    f"Expected is_bot to be true, got false")
            return v

        def get_user_id(self) -> str:
            return self.user_id

    class Event(BaseModel):
        type: str
        team: str
        user: str
        channel: str
        channel_type: str
        blocks: List[MessageBlock]

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

    authorizations: List[Authorization]
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
        Returns team ID of the given event request.
        """
        return self.event.team

    def get_user_id(self) -> str:
        """
        Returns user ID of the given event request.
        """
        return self.event.user

    def get_channel_id(self) -> str:
        """
        Returns channel ID of the event given requeest.
        """
        return self.event.channel

    def is_created_by_human_user(self) -> bool:
        """
        Returns True if message is created by human user and False otherwise.
        """
        for auth in self.authorizations:
            if auth.get_user_id() == self.get_user_id():
                # Message created by bot.
                return False
        return True


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
    view: BaseModalView

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

            if message_event_request.is_created_by_human_user():
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

    try:
        payload = InteractionPayload(**payload_dict)
        if payload.is_message_shortcut():
            # Handle Shortcut message.
            shortcut_payload = MessageShortcutPayload(**payload_dict)
            if shortcut_payload.is_create_doc_shortcut():
                # User wants to add a section to the documentation.
                create_doc_from_message_shortcut_in_background.delay(
                    shortcut_payload.model_dump_json())
        elif payload.is_global_shortcut():
            global_shortcut_payload = GlobalShortcutPayload(**payload_dict)
            if global_shortcut_payload.get_callback_id() == GlobalShortcutPayload.CREATE_DOC_CALLBACK_ID:
                create_doc_from_global_shortcut_in_background.delay(
                    global_shortcut_payload.model_dump_json(exclude_none=True))
            elif global_shortcut_payload.get_callback_id() == GlobalShortcutPayload.EDIT_DOC_CALLBACK_ID:
                edit_doc_from_shortcut_in_background.delay(
                    global_shortcut_payload.model_dump_json(exclude_none=True))

        elif payload.is_view_interaction():
            # Handle Modal View closing or submission.
            if payload.is_view_closed():
                cancel_payload = CancelPayload(**payload_dict)
                if cancel_payload.get_view_title() == CreateDocViewFactory.get_view_title():
                    # User has closed the Create Doc view.
                    cancel_payload = CancelPayload(**payload_dict)
                    view_id = cancel_payload.get_view_id()

                    delete_upload_in_background.delay(view_id)
            elif payload.is_view_submission():
                # User has submitted the view.
                submission_payload = SubmissionPayload(**payload_dict)
                if submission_payload.get_view_title() == CreateDocViewFactory.get_view_title():
                    # The view submitted is the Create Section view.
                    create_doc_payload = CreateDocSubmissionPayload(
                        **payload_dict)
                    view_id = create_doc_payload.get_view_id()
                    heading = create_doc_payload.get_heading_plain_text()
                    body = create_doc_payload.get_body_markdown()
                    team_domain: str = create_doc_payload.get_team_domain()

                    pages_within_team: List[SlackSection] = userport.db.get_slack_pages_within_team(
                        team_domain=team_domain)

                    update_upload_in_background.delay(
                        view_id, heading, body)

                    # Return an updated view asking user where to place the added section.
                    view_update_response = ViewUpdateResponse(
                        view=PlaceDocViewFactory().create_with_page_options(
                            pages_within_team)
                    )

                    return view_update_response.model_dump(exclude_none=True), 200
                elif submission_payload.get_view_title() == PlaceDocViewFactory.get_view_title():
                    if PlaceDocSubmissionPayload(**payload_dict).is_new_page_submission():
                        new_page_submission_payload = PlaceDocNewPageSubmissionPayload(
                            **payload_dict)

                        new_page_title = new_page_submission_payload.get_new_page_title()
                        view_id = new_page_submission_payload.get_view_id()
                        create_new_page_in_background.delay(
                            view_id=view_id, new_page_title=new_page_title)
                    else:
                        placed_doc_submission = PlaceDocSelectParentOrPositionState(
                            **payload_dict)
                        create_section_inside_page_in_background.delay(
                            placed_doc_submission.model_dump_json(
                                exclude_none=True)
                        )
                elif submission_payload.get_view_title() == EditDocViewFactory.get_view_title():
                    update_edited_section_in_background.delay(
                        EditDocBlockAction(**payload_dict).model_dump_json(exclude_none=True))

        elif payload.is_block_actions():
            # Handle Block Elements related updates within a view.
            block_actions_payload = BlockActionsPayload(**payload_dict)
            if block_actions_payload.is_page_selection_action_id():

                select_menu_actions_payload = SelectMenuBlockActionsPayload(
                    **payload_dict)
                if len(select_menu_actions_payload.actions) != 1:
                    raise ValueError(
                        f"Expected 1 action in payload, got {select_menu_actions_payload} instead")
                selected_menu_action = select_menu_actions_payload.actions[0]
                selected_menu_actions_json = select_menu_actions_payload.model_dump_json(
                    exclude_none=True)

                if block_actions_payload.is_page_selection_action_id():
                    # User has selected a Page to the add new section to.
                    if PlaceDocViewFactory.is_create_new_page_action(selected_menu_action):
                        # Return an updated view asking user for new page title input.
                        update_view_with_new_page_title_in_background.delay(
                            selected_menu_actions_json)
                    else:
                        # Return updated view with options to place view in page.
                        update_view_with_place_document_selected_page_in_background.delay(
                            selected_menu_actions_json)
            elif block_actions_payload.is_parent_section_selection_action_id():
                parent_state_json = PlaceDocSelectParentOrPositionState(
                    **payload_dict).model_dump_json(exclude_none=True)
                # User has selected parent section.
                update_view_with_parent_section_in_background.delay(
                    parent_state_json)
            elif block_actions_payload.is_position_selection_action_id():
                position_state_json = PlaceDocSelectParentOrPositionState(
                    **payload_dict).model_dump_json(exclude_none=True)
                # User has selected insertion position of new section.
                update_view_with_new_layout_in_background.delay(
                    position_state_json)
            elif block_actions_payload.is_edit_select_page_action_id():
                edit_doc_block_action = EditDocBlockAction(**payload_dict)
                # User has selected page to edit.
                display_edit_view_with_sections.delay(
                    edit_doc_block_action.model_dump_json(exclude_none=True))
            elif block_actions_payload.is_edit_select_section_action_id():
                edit_doc_block_action = EditDocBlockAction(**payload_dict)
                # Display section to edit.
                display_edited_section.delay(
                    edit_doc_block_action.model_dump_json(exclude_none=True))

    except Exception as e:
        print(f"Encountered error: {e} when parsing payload: {payload_dict}")
        return interal_error_message, 200

    return "", 200


@bp.route('/<team_domain>/<path:subpath>', methods=['GET'])
def render_documentation_page(team_domain: str, subpath: str):
    # Remove / in the subpath.
    page_html_section_id = escape(subpath).replace("/", "")

    html_generator = SlackHTMLGenerator()
    page_html: str = html_generator.get_page(team_domain=team_domain,
                                             page_html_section_id=page_html_section_id)

    return page_html, 200


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def answer_user_query_in_background(user_query: str, team_id: str, channel_id: str, user_id: str, private_visibility: bool):
    slack_inference = SlackInference(hostname_url=HARDCODED_HOSTNAME)
    answer_blocks: List[MessageBlock] = slack_inference.answer(
        user_query=user_query, team_id=team_id)
    answer_dicts = [block.model_dump(exclude_none=True)
                    for block in answer_blocks]

    # Post answer to user as a chat message.
    web_client = get_slack_web_client()
    if private_visibility:
        # Post ephemeral message.
        web_client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            blocks=answer_dicts,
        )
    else:
        # Post public message.
        # User user_id as channel argument for IMs per: https://api.slack.com/methods/chat.postMessage#app_home
        # TODO: Change this once we can post public messages in channels as well (in addtion to just IMs). Be careful
        # to not respond to bot posted messages and enter into a recursive loop like we observed in DMs.
        web_client.chat_postMessage(
            channel=user_id,
            blocks=answer_dicts
        )


def _create_doc_common_in_background(common_payload: CommonShortcutPayload, initial_rich_text_block: RichTextBlock = None):
    """
    Helper method to create documentation either from Message or Global shortcut
    in background Celery task.
    """
    # Create view.
    view = CreateDocViewFactory().create_view(
        initial_body_value=initial_rich_text_block)
    web_client = get_slack_web_client()
    slack_response: SlackResponse = web_client.views_open(
        trigger_id=common_payload.get_trigger_id(), view=view.model_dump(exclude_none=True))
    view_response = ViewCreatedResponse(**slack_response.data)

    # Create upload in db.
    user_id = common_payload.get_user_id()
    team_id = common_payload.get_team_id()
    team_domain = common_payload.get_team_domain()
    shortcut_callback_id = common_payload.get_callback_id()
    view_id = view_response.get_id()
    userport.db.create_slack_upload(creator_id=user_id, team_id=team_id, team_domain=team_domain, view_id=view_id,
                                    shortcut_callback_id=shortcut_callback_id)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def create_doc_from_message_shortcut_in_background(create_doc_shortcut_json: str):
    """
    Create View and write Slack upload to db after user initiates 
    documentation creation from Message Shortcut.

    There will be an initial body since the documentation is created from
    Message itself.

    We do this in Celery task since it can take > 3s in API path and
    result in user seeing an operation_timeout error message in the Slack channel.
    """
    create_doc_dict = json.loads(create_doc_shortcut_json)
    common_payload = CommonShortcutPayload(**create_doc_dict)
    initial_rich_text_block = MessageShortcutPayload(
        **create_doc_dict).get_rich_text_block()
    _create_doc_common_in_background(
        common_payload=common_payload, initial_rich_text_block=initial_rich_text_block)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def create_doc_from_global_shortcut_in_background(create_doc_global_shortcut_json: str):
    """
    Create View and write Slack upload to db after user initiates 
    documentation creation from Global shortcut.

    There won't be any initial body unlike in Message shortcut.

    We do this in Celery task since it can take > 3s in API path and
    result in user seeing an operation_timeout error message in the Slack channel.
    """
    common_payload = CommonShortcutPayload(
        **json.loads(create_doc_global_shortcut_json))
    _create_doc_common_in_background(common_payload=common_payload)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def edit_doc_from_shortcut_in_background(edit_doc_shortcut_json: str):
    """
    User has requested to edit shortcut, create a view and allow them to do it.
    """
    edit_doc_shortcut = GlobalShortcutPayload(
        **json.loads(edit_doc_shortcut_json))

    view = EditDocViewFactory().create_initial_view(
        team_domain=edit_doc_shortcut.get_team_domain())
    web_client = get_slack_web_client()
    web_client.views_open(
        trigger_id=edit_doc_shortcut.get_trigger_id(), view=view.model_dump(exclude_none=True))


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def display_edit_view_with_sections(edit_doc_block_action_json: str):
    """
    User has requested sections within a given page. We will update the view to
    display the sections.
    """
    edit_doc_block_action = EditDocBlockAction(
        **json.loads(edit_doc_block_action_json))

    final_view = EditDocViewFactory().update_view_with_page_layout(edit_doc_block_action)

    web_client = get_slack_web_client()
    web_client.views_update(
        view_id=edit_doc_block_action.get_view_id(),
        hash=edit_doc_block_action.get_view_hash(),
        view=final_view.model_dump(exclude_none=True),
    )


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def display_edited_section(edit_doc_block_action_json: str):
    """
    Display Edited section by user.
    """
    edit_doc_block_action = EditDocBlockAction(
        **json.loads(edit_doc_block_action_json))

    # Remove existing section view if any.
    first_view = EditDocViewFactory().remove_existing_section_info(edit_doc_block_action)
    web_client = get_slack_web_client()
    web_client.views_update(
        view_id=edit_doc_block_action.get_view_id(),
        hash=edit_doc_block_action.get_view_hash(),
        view=first_view.model_dump(exclude_none=True),
    )

    # Add new section.
    section_view = EditDocViewFactory().fetch_section_info(edit_doc_block_action)
    web_client = get_slack_web_client()
    # Not using Hash in the argument because it causes conflict. This is likely
    # because the view hash has been updated in the first view update call above.
    web_client.views_update(
        view_id=edit_doc_block_action.get_view_id(),
        view=section_view.model_dump(exclude_none=True),
    )


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def update_edited_section_in_background(edit_doc_block_action_json: str):
    """
    Update Edited section in the database.
    """
    edit_doc_block_action = EditDocBlockAction(
        **json.loads(edit_doc_block_action_json))

    # Find heading level from existing section.
    section_id = edit_doc_block_action.get_section_id()
    section_heading_plain_text = edit_doc_block_action.get_section_heading()
    section = userport.db.get_slack_section(section_id)
    heading_level = userport.utils.get_heading_level(section.heading)
    section_heading_markdown = userport.utils.convert_to_markdown_heading(
        text=section_heading_plain_text, level=heading_level)
    section_body_markdown = edit_doc_block_action.get_section_body_block().get_markdown()

    # Update database.
    find_request = FindSlackSectionRequest(id=ObjectId(section_id))
    update_request = UpdateSlackSectionRequest(
        heading=section_heading_markdown,
        text=section_body_markdown,
    )
    find_and_update_request = FindAndUpateSlackSectionRequest(
        find_request=find_request, update_request=update_request)
    userport.db.update_slack_sections([find_and_update_request])

    # Re-index the page.
    indexer = SlackPageIndexer()
    indexer.run_from_section(section_id=section_id)


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
    payload = SelectMenuBlockActionsPayload(
        **json.loads(select_menu_block_actions_payload_json))
    pages_within_team: List[SlackSection] = userport.db.get_slack_pages_within_team(
        team_domain=payload.get_team_domain()
    )
    final_modal_view = PlaceDocViewFactory().create_with_new_page_option_selected(
        pages_within_team=pages_within_team
    ).model_dump(exclude_none=True)

    web_client = get_slack_web_client()
    web_client.views_update(
        view_id=payload.get_view_id(),
        hash=payload.get_view_hash(),
        view=final_modal_view,
    )


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def update_view_with_place_document_selected_page_in_background(select_menu_block_actions_payload_json: str):
    """
    Update View showing user place document view with selected page.

    Performed in Celery task so API call path can complete in less than 3s.
    """
    payload = SelectMenuBlockActionsPayload(
        **json.loads(select_menu_block_actions_payload_json))
    selected_option = payload.actions[0].get_selected_option()
    pages_within_team: List[SlackSection] = userport.db.get_slack_pages_within_team(
        team_domain=payload.get_team_domain()
    )
    final_modal_view = PlaceDocViewFactory().create_with_selected_page(
        pages_within_team=pages_within_team,
        selected_option=selected_option
    ).model_dump(exclude_none=True)

    web_client = get_slack_web_client()
    web_client.views_update(
        view_id=payload.get_view_id(),
        hash=payload.get_view_hash(),
        view=final_modal_view,
    )


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def update_view_with_parent_section_in_background(parent_state_json: str):
    """
    Update View with parent section selection by user.

    Performed in Celery task so API call path can complete in less than 3s.
    """
    parent_state = PlaceDocSelectParentOrPositionState(
        **json.loads(parent_state_json))

    final_modal_view = PlaceDocViewFactory().create_with_selected_parent_section(
        parent_state=parent_state).model_dump(exclude_none=True)

    web_client = get_slack_web_client()
    web_client.views_update(
        view_id=parent_state.get_view_id(),
        hash=parent_state.get_view_hash(),
        view=final_modal_view,
    )


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def update_view_with_new_layout_in_background(position_state_json: str):
    """
    Update View with new layout given that user has selected insertion position of created section.

    Performed in Celery task so API call path can complete in less than 3s.
    """
    position_state = PlaceDocSelectParentOrPositionState(
        **json.loads(position_state_json))

    final_modal_view = PlaceDocViewFactory().create_with_selected_position(
        position_state=position_state).model_dump(exclude_none=True)

    web_client = get_slack_web_client()
    web_client.views_update(
        view_id=position_state.get_view_id(),
        hash=position_state.get_view_hash(),
        view=final_modal_view,
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
    team_domain: str = slack_upload.team_domain
    creator_id: str = slack_upload.creator_id
    section_heading_plain_text: str = slack_upload.heading_plain_text
    section_text_markdown: str = slack_upload.text_markdown

    # Get creator email.
    web_client = get_slack_web_client()
    slack_response: SlackResponse = web_client.users_info(user=creator_id)
    creator_email: str = UserInfoResponse(
        **slack_response.data).get_email()

    # Create Slack Section for both section and page.
    page_html_section_id: str = userport.utils.convert_to_url_path_text(
        text=new_page_title)
    page_section = SlackSection(
        upload_id=upload_id,
        team_id=team_id,
        team_domain=team_domain,
        creator_id=creator_id,
        creator_email=creator_email,
        updater_id=creator_id,
        updater_email=creator_email,
        heading=userport.utils.convert_to_markdown_heading(
            text=new_page_title, level=1),
        html_section_id=page_html_section_id,
        page_html_section_id=page_html_section_id,
    )
    child_html_section_id: str = userport.utils.convert_to_url_path_text(
        text=section_heading_plain_text)
    child_section = SlackSection(
        upload_id=upload_id,
        team_id=team_id,
        team_domain=team_domain,
        creator_id=creator_id,
        creator_email=creator_email,
        updater_id=creator_id,
        updater_email=creator_email,
        heading=userport.utils.convert_to_markdown_heading(
            text=section_heading_plain_text, level=2),
        text=section_text_markdown,
        html_section_id=child_html_section_id,
        page_html_section_id=page_html_section_id,
    )

    # Write sections to database.
    page_id, child_id = userport.db.create_slack_page_and_section(
        page_section=page_section, child_section=child_section)

    # Complete upload in background.
    uploaded_url = userport.utils.create_documentation_url(
        host_name=HARDCODED_HOSTNAME,
        team_domain=team_domain,
        page_html_id=page_html_section_id,
        section_html_id=child_html_section_id
    )
    complete_new_section_upload_in_background.delay(
        upload_id, page_id, uploaded_url)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def create_section_inside_page_in_background(placed_doc_submission_json):
    """
    Create Section within existing page and complete upload of the section in the background.
    """
    placed_doc_submission = PlaceDocSelectParentOrPositionState(
        **json.loads(placed_doc_submission_json))
    page_id: str = placed_doc_submission.get_page_id()
    parent_section_id: str = placed_doc_submission.get_parent_section_id()
    position: int = placed_doc_submission.get_position()
    view_id: str = placed_doc_submission.get_view_id()

    slack_upload: SlackUpload
    try:
        slack_upload = userport.db.get_slack_upload_from_view_id(
            view_id=view_id)
    except userport.db.NotFoundException as e:
        logging.error(
            f"Section insertion into existing page failed for submission: {placed_doc_submission} with error: {e}")
        return

     # Gather information from upload.
    upload_id: str = slack_upload.id
    team_id: str = slack_upload.team_id
    team_domain: str = slack_upload.team_domain
    creator_id: str = slack_upload.creator_id
    section_heading_plain_text: str = slack_upload.heading_plain_text
    section_text_markdown: str = slack_upload.text_markdown

    # Get creator email.
    web_client = get_slack_web_client()
    slack_response: SlackResponse = web_client.users_info(user=creator_id)
    creator_email: str = UserInfoResponse(
        **slack_response.data).get_email()

    # Create new section object and insert into parent section as child.
    page_section = userport.db.get_slack_section(id=page_id)
    child_html_section_id: str = userport.utils.convert_to_url_path_text(
        text=section_heading_plain_text)
    parent_section = userport.db.get_slack_section(id=parent_section_id)
    # Child heading level is 1+ parent heading level.
    child_heading_level: int = userport.utils.get_heading_level(
        parent_section.heading) + 1
    child_section = SlackSection(
        upload_id=upload_id,
        parent_section_id=parent_section_id,
        page_id=page_id,
        team_id=team_id,
        team_domain=team_domain,
        creator_id=creator_id,
        creator_email=creator_email,
        updater_id=creator_id,
        updater_email=creator_email,
        heading=userport.utils.convert_to_markdown_heading(
            text=section_heading_plain_text, level=child_heading_level),
        text=section_text_markdown,
        html_section_id=child_html_section_id,
        page_html_section_id=page_section.html_section_id,
    )
    child_id = userport.db.insert_section_in_parent(
        child_section=child_section, parent_section_id=parent_section_id, position=position)

    # Complete upload in background.
    uploaded_url = userport.utils.create_documentation_url(
        host_name=HARDCODED_HOSTNAME,
        team_domain=team_domain,
        page_html_id=page_section.html_section_id,
        section_html_id=child_html_section_id
    )
    complete_new_section_upload_in_background.delay(
        upload_id, child_id, uploaded_url)


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 5})
def complete_new_section_upload_in_background(upload_id: str, section_id: str, uploaded_url: str):
    """
    Complete upload process so that the given section (and sections below in the same page) can be indexed for retrieval.

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

    web_client = get_slack_web_client()

    if slack_upload.status != SlackUploadStatus.IN_PROGRESS:
        # Post ephemeral message to user's DM with Knobo.
        web_client.chat_postEphemeral(channel=slack_upload.creator_id, user=slack_upload.creator_id,
                                      text="Documentation creation is in progress! I will ping you once it's done!")

        userport.db.update_slack_upload_status(
            upload_id=upload_id, upload_status=SlackUploadStatus.IN_PROGRESS)
        logging.info("Updated Upload Status to in progress successfully")

    if slack_upload.status != SlackUploadStatus.COMPLETED:
        # Index the page and associated section.
        indexer = SlackPageIndexer()
        indexer.run_from_section(section_id=section_id)

        userport.db.update_slack_upload_status(
            upload_id=upload_id, upload_status=SlackUploadStatus.COMPLETED)
        logging.info("Updated Upload Status to in Completed successfully")

    # Post ephemeral message to user's DM with Knobo.
    web_client.chat_postEphemeral(channel=slack_upload.creator_id, user=slack_upload.creator_id,
                                  text=f"Documentation upload complete! Available at {uploaded_url}")
