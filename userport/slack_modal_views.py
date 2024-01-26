from typing import ClassVar, List, Union
from pydantic import BaseModel, validator
from userport.slack_blocks import (
    RichTextBlock,
    TextObject,
    InputBlock,
    PlainTextInputElement,
    RichTextInputElement,
    RichTextSectionElement,
    RichTextObject,
    SelectMenuStaticElement,
    SelectOptionObject
)

"""
Module contains helper classes to manage creation and parsing of Slack Modal Views.

Reference: https://api.slack.com/reference/interaction-payloads/views#view_submission_fields
"""


class InteractionPayload(BaseModel):
    """
    Common class for Message Shortcut, View submission or View Cancel payloads.

    Reference: https://api.slack.com/surfaces/modals#interactions
    """
    class SlackTeam(BaseModel):
        id: str

    class SlackUser(BaseModel):
        id: str

    type: str
    team: SlackTeam
    user: SlackUser

    def is_view_interaction(self) -> bool:
        return self.type.startswith("view")

    def is_view_closed(self) -> bool:
        return self.type == "view_closed"

    def is_view_submission(self) -> bool:
        return self.type == "view_submission"

    def is_message_shortcut(self) -> bool:
        return self.type == "message_action"

    def is_block_actions(self) -> bool:
        return self.type == "block_actions"


class CommonView(BaseModel):
    """
    Common class for View objects.

    Reference: https://api.slack.com/reference/surfaces/views
    """
    class Title(BaseModel):
        text: str

    id: str
    title: Title
    # hash is used to avoid race conditions when calling view.update.
    # https://api.slack.com/surfaces/modals#handling_race_conditions
    hash: str

    def get_id(self) -> str:
        return self.id

    def get_title(self) -> str:
        return self.title.text


class ViewCreatedResponse(BaseModel):
    """
    Class containing fields we care about in View creation response.

    Reference: https://api.slack.com/methods/views.open#examples
    """
    view: CommonView

    def get_id(self) -> str:
        return self.view.get_id()


class CancelPayload(InteractionPayload):
    """
    Class containing fields we care about in View Cancel payload.
    """
    view: CommonView

    def get_view_id(self):
        """
        Returns View ID.
        """
        return self.view.get_id()


class SubmissionPayload(InteractionPayload):
    """
    Class containing fields we care about in View submission payload.
    """
    view: CommonView

    def get_title(self) -> str:
        return self.view.get_title()


class BlockActionsPayload(InteractionPayload):
    """
    Class containing fields we care about in a general Block Actions payload.
    """
    class GeneralAction(BaseModel):
        action_id: str

    actions: List[GeneralAction]

    def is_page_selection_action_id(self) -> bool:
        """
        Returns True if page selection action ID, False otherwise.
        """
        return len(self.actions) > 0 and self.actions[0].action_id == PlaceDocModalView.PAGE_SELECTION_ACTION_ID


class SelectMenuBlockActionsPayload(InteractionPayload):
    """
    Class containing fields we care about in the Select Menu based Block Actions payload.
    """
    class SelectMenuAction(BaseModel):
        class SelectedOption(BaseModel):
            text: TextObject
            value: str

        type: str
        action_id: str
        block_id: str
        selected_option: SelectedOption

    actions: List[SelectMenuAction]


class CreateDocState(BaseModel):
    """
    State associated with Create Document view submission.

    The structure is derived from the actual payload we receive from Slack.
    """
    class Values(BaseModel):
        class HeadingBlock(BaseModel):
            class HeadingBlockValue(BaseModel):
                type: str
                value: str

                @validator("type")
                def validate_type(cls, v):
                    if v != 'plain_text_input':
                        raise ValueError(
                            f"Expected 'plain_text_input' as type value for HeadingBlockValue, got {v}")
                    return v

            create_doc_heading_value: HeadingBlockValue

        class BodyBlock(BaseModel):
            class BodyBlockValue(BaseModel):
                type: str
                rich_text_value: RichTextBlock

                @validator("type")
                def validate_type(cls, v):
                    if v != 'rich_text_input':
                        raise ValueError(
                            f"Expected 'rich_text_input' as type value for BodyBlockValue, got {v}")
                    return v

            create_doc_body_value: BodyBlockValue

        create_doc_heading: HeadingBlock
        create_doc_body: BodyBlock

    values: Values

    def get_heading_markdown(self) -> str:
        """
        Get heading as Markdown formatted text.

        We will convert it to a Heading 2 for now.
        TODO: The heading number should be based on which section
        the user wants to insert the text.
        """
        return f'## {self.values.create_doc_heading.create_doc_heading_value.value}'

    def get_body_markdown(self) -> str:
        """
        Get body as Markdown formatted text.
        """
        return self.values.create_doc_body.create_doc_body_value.rich_text_value.get_markdown()


class CreateDocSubmissionView(CommonView):
    """
    Atttributes in View submission view.
    """
    state: CreateDocState

    def get_id(self) -> str:
        return self.id

    def get_heading_markdown(self) -> str:
        return self.state.get_heading_markdown()

    def get_body_markdown(self) -> str:
        return self.state.get_body_markdown()


class CreateDocSubmissionPayload(InteractionPayload):
    """
    Attributes in Create Document View submission payload. 
    """
    view: CreateDocSubmissionView

    def get_view_id(self) -> str:
        """
        Return View ID.
        """
        return self.view.get_id()

    def get_team_id(self) -> str:
        """
        Return ID of the Slack Workspace.
        """
        return self.team.id

    def get_user_id(self) -> str:
        """
        Return ID of the Slack user trying to create the doc.
        """
        return self.user.id

    def get_title(self) -> str:
        """
        Return title of the View which also
        serves as identifier for the View type.
        """
        return self.view.get_title()

    def get_heading_markdown(self) -> str:
        """
        Get Heading as Markdown formatted text.
        """
        return self.view.get_heading_markdown()

    def get_body_markdown(self) -> str:
        """
        Get body as Markdown formatted text.
        """
        return self.view.get_body_markdown()


class ShortcutMessage(BaseModel):
    """
    Slack Message received in Message Short Payload.
    """
    TYPE_VALUE: ClassVar[str] = "message"

    type: str
    blocks: List[RichTextBlock]

    @validator("type")
    def validate_type(cls, v):
        if v != ShortcutMessage.TYPE_VALUE:
            raise ValueError(
                f"Expected {ShortcutMessage.TYPE_VALUE} element type, got {v}")
        return v

    @validator("blocks")
    def validate_blocks(cls, v):
        # Even though this is a list, practically we observe only
        # 1 element present in the shortcut payload.
        if len(v) != 1:
            raise ValueError(
                f"Expected 1 element in 'blocks' attribute, got {v}")
        return v

    def get_rich_text_block(self) -> RichTextBlock:
        """
        Return Rich text block in message.
        """
        return self.blocks[0]

    def get_markdown(self) -> str:
        """
        Return text in markdown format.
        """
        return self.get_rich_text_block().get_markdown()


class MessageShortcutPayload(InteractionPayload):
    """
    Class containing fields we care about in the Message Shortcut payload.
    """
    CREATE_DOC_CALLBACK_ID: ClassVar[str] = 'create_doc_from_message'

    class Channel(BaseModel):
        id: str

    message: ShortcutMessage
    response_url: str
    callback_id: str
    trigger_id: str
    channel: Channel
    message_ts: str

    def get_team_id(self) -> str:
        """
        Return ID of the Slack Workspace.
        """
        return self.team.id

    def get_user_id(self) -> str:
        """
        Return ID of the Slack user trying to create the doc.
        """
        return self.user.id

    def get_response_url(self) -> str:
        """
        Return Response URL associated with the payload.
        """
        return self.response_url

    def get_trigger_id(self) -> str:
        """
        Return Trigger ID of the pyload.
        """
        return self.trigger_id

    def get_callback_id(self) -> str:
        """
        Return Callback ID of the pyload. It is the identifier
        for the Shortcut.
        """
        return self.callback_id

    def get_message_ts(self) -> str:
        """
        Return Message ID of the pyload. It is the identifier
        for the Message that the shortcut is derived from.
        """
        return self.message_ts

    def get_channel_id(self) -> str:
        """
        Return Channel ID of the pyload. It is the identifier
        for the Channel that the shortcut is derived from.
        """
        return self.channel.id

    def is_create_doc_shortcut(self) -> bool:
        """
        Returns True if payload is for Create Doc Shortcut and False otherwise.
        """
        return self.callback_id == MessageShortcutPayload.CREATE_DOC_CALLBACK_ID

    def get_rich_text_block(self) -> RichTextBlock:
        """
        Return Rich Text block in Message.
        """
        return self.message.get_rich_text_block()

    def get_markdown(self) -> str:
        """
        Return shortcut message in markdown format.
        """
        return self.message.get_markdown()


class PlainTextObject(TextObject):
    """
    Only Plain Text objects less than 24 characters in length allowed.
    """
    type: str = "plain_text"

    @validator("type")
    def validate_title_type(cls, v):
        if v != "plain_text":
            raise ValueError(
                f"Expected 'plain_text' element type, got {v}")
        return v

    @validator("text")
    def validate_type(cls, v):
        if len(v) > 24:
            raise ValueError(
                f"Expected text to be max 24 chars in length, got {v}")
        return v


class BaseModalView(BaseModel):
    """
    Base Class to represent a Modal View object.

    Reference: https://api.slack.com/reference/surfaces/views
    """
    MODAL_VALUE: ClassVar[str] = "modal"

    type: str = MODAL_VALUE
    title: PlainTextObject
    blocks: List[Union[InputBlock, RichTextBlock]]
    submit: PlainTextObject
    close: PlainTextObject
    notify_on_close: bool = True

    @validator("type")
    def validate_type(cls, v):
        if v != BaseModalView.MODAL_VALUE:
            raise ValueError(
                f"Expected {BaseModalView.MODAL_VALUE} element type, got {v}")
        return v


class CreateDocModalView(BaseModalView):
    """
    Class that takes creates a view to ask for section heading and 
    content inputs from a user.
    """
    VIEW_TITLE: ClassVar[str] = "Create Section"

    INFORMATION_BLOCK_ID: ClassVar[str] = "create_doc_info"

    HEADING_TEXT: ClassVar[str] = "Heading"
    HEADING_BLOCK_ID: ClassVar[str] = "create_doc_heading"
    HEADING_ELEMENT_ACTION_ID: ClassVar[str] = "create_doc_heading_value"

    BODY_TEXT: ClassVar[str] = "Body"
    BODY_BLOCK_ID: ClassVar[str] = "create_doc_body"
    BODY_ELEMENT_ACTION_ID: ClassVar[str] = "create_doc_body_value"

    SUBMIT_TEXT: ClassVar[str] = "Next"
    CLOSE_TEXT: ClassVar[str] = "Cancel"

    @staticmethod
    def get_view_title() -> str:
        """
        Helper to fetch Title of Create Documentation modal view.
        """
        return CreateDocModalView.VIEW_TITLE


def create_document_view(initial_body_value: RichTextBlock) -> CreateDocModalView:
    """
    Returns view for Create document with given initial value for section body.
    """
    return CreateDocModalView(
        title=PlainTextObject(text=CreateDocModalView.get_view_title()),
        blocks=[
            RichTextBlock(
                block_id=CreateDocModalView.INFORMATION_BLOCK_ID,
                elements=[
                    RichTextSectionElement(
                        elements=[
                            RichTextObject(
                                type=RichTextObject.TYPE_TEXT,
                                text="You are about to create a new section with a heading and associated body that will be added to the documentation." +
                                " Once both fields are filled, please click Next. You can abort this operation by clicking Cancel."
                            )
                        ]
                    )
                ],
            ),
            InputBlock(
                label=PlainTextObject(text=CreateDocModalView.HEADING_TEXT),
                block_id=CreateDocModalView.HEADING_BLOCK_ID,
                element=PlainTextInputElement(
                    action_id=CreateDocModalView.HEADING_ELEMENT_ACTION_ID)
            ),
            InputBlock(
                label=PlainTextObject(text=CreateDocModalView.BODY_TEXT),
                block_id=CreateDocModalView.BODY_BLOCK_ID,
                element=RichTextInputElement(
                    action_id=CreateDocModalView.BODY_ELEMENT_ACTION_ID,
                    initial_value=initial_body_value,
                )
            )
        ],
        submit=PlainTextObject(text=CreateDocModalView.SUBMIT_TEXT),
        close=PlainTextObject(text=CreateDocModalView.CLOSE_TEXT),
    )


class PlaceDocModalView(BaseModalView):
    """
    Class that asks user to assign placement of Documentation Section
    in the previous view.
    """
    VIEW_TITLE: ClassVar[str] = "Select Location"

    PAGE_SELECTION_LABEL_TEXT: ClassVar[str] = "Select Page"
    PAGE_SELECTION_BLOCK_ID: ClassVar[str] = "page_selection_block_id"
    PAGE_SELECTION_ACTION_ID: ClassVar[str] = "page_selection_action_id"

    SUBMIT_TEXT: ClassVar[str] = "Submit"
    CLOSE_TEXT: ClassVar[str] = "Cancel"

    @staticmethod
    def get_view_title() -> str:
        """
        Helper to fetch Title of Place Documentation modal view.
        """
        return PlaceDocModalView.VIEW_TITLE


def place_document_view() -> PlaceDocModalView:
    """
    Returns Modal View to place created section from previous view.
    """
    return PlaceDocModalView(
        title=PlainTextObject(text=PlaceDocModalView.VIEW_TITLE),
        blocks=[
            RichTextBlock(
                block_id="place_doc_info",
                elements=[
                    RichTextSectionElement(
                        elements=[
                            RichTextObject(
                                type=RichTextObject.TYPE_TEXT,
                                text="Please select the Page where you want to add this section.\n\n" +
                                     "If you select \"New Page\", then please provide a Page Title as well."
                            )
                        ]
                    ),
                ],
            ),
            InputBlock(
                label=PlainTextObject(
                    text=PlaceDocModalView.PAGE_SELECTION_LABEL_TEXT),
                block_id=PlaceDocModalView.PAGE_SELECTION_BLOCK_ID,
                element=SelectMenuStaticElement(
                    action_id=PlaceDocModalView.PAGE_SELECTION_ACTION_ID,
                    options=[
                        SelectOptionObject(
                            text=TextObject(
                                type=TextObject.TYPE_PLAIN_TEXT, text="New Page"),
                            value="new_page_id",
                        ),
                        SelectOptionObject(
                            text=TextObject(
                                type=TextObject.TYPE_PLAIN_TEXT, text="FAQs"),
                            value="xyz_id",
                        )
                    ]
                ),
                dispatch_action=True,
            ),
        ],
        submit=PlainTextObject(text=PlaceDocModalView.SUBMIT_TEXT),
        close=PlainTextObject(text=PlaceDocModalView.CLOSE_TEXT),
    )
