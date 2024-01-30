from typing import ClassVar, List, Union, Dict
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

    def get_hash(self) -> str:
        return self.hash


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

    def get_view_title(self) -> str:
        """
        Get View Title of given View submission Payload.
        """
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


class SelectedOptionText(BaseModel):
    """
    Text associated with selected option by user.
    """
    text: TextObject
    value: str

    def get_value(self) -> str:
        return self.value


class SelectMenuAction(BaseModel):
    """
    Class containing Select Menu Action attributes.
    Associated with SelectMenuBlockActionsPayload defined below.
    """
    type: str
    action_id: str
    block_id: str
    selected_option: SelectedOptionText

    def get_action_id(self) -> str:
        """
        Action ID for given Select Menu Action.
        """
        return self.action_id

    def get_selected_option_id(self) -> str:
        """
        Returns ID of the selected option for given Select Menu Action.
        """
        return self.selected_option.get_value()


class SelectMenuBlockActionsPayload(InteractionPayload):
    """
    Class containing fields we care about in the Select Menu based Block Actions payload.
    """
    view: CommonView

    actions: List[SelectMenuAction]

    def get_view_id(self):
        return self.view.get_id()

    def get_view_hash(self):
        return self.view.get_hash()


class InputPlainTextValue(BaseModel):
    """
    Value input by user in plain text in a view.
    """
    TYPE_VALUE: ClassVar[str] = 'plain_text_input'
    type: str
    value: str

    @validator("type")
    def validate_type(cls, v):
        if v != InputPlainTextValue.TYPE_VALUE:
            raise ValueError(
                f"Expected {InputPlainTextValue.TYPE_VALUE} as type value, got {v}")
        return v

    def get_value(self) -> str:
        return self.value


class CreateDocState(BaseModel):
    """
    State associated with Create Document view submission.

    The structure is derived from the actual payload we receive from Slack.
    """
    class Values(BaseModel):
        class HeadingBlock(BaseModel):
            create_doc_heading_value: InputPlainTextValue

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

    def get_heading_plain_text(self) -> str:
        """
        Get heading as plain text (unformatted).

        Unlike body, we won't format as Markdown because Heading tag (h1,h2 tc)
        will depend on placement of the section within a page.
        """
        return self.values.create_doc_heading.create_doc_heading_value.value

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

    def get_heading_plain_text(self) -> str:
        return self.state.get_heading_plain_text()

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

    def get_heading_plain_text(self) -> str:
        """
        Get Heading as Markdown formatted text.
        """
        return self.view.get_heading_plain_text()

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

    class SelectOptionData(BaseModel):
        """
        Class to hold selection Option data.
        This includes text and ID of the option.
        """
        text: str
        id: str

    VIEW_TITLE: ClassVar[str] = "Select Location"

    PLACE_DOC_INFO_BLOCK_ID: ClassVar[str] = "place_doc_info_block_id"
    PLACE_DOC_INFO_TEXT: ClassVar[str] = "Please select the Page where you want to add this section.\n\n" + \
        "If you select \"Create New Page\", then please provide a New Page Title as well."

    PAGE_SELECTION_LABEL_TEXT: ClassVar[str] = "Select Page"
    PAGE_SELECTION_BLOCK_ID: ClassVar[str] = "page_selection_block_id"
    PAGE_SELECTION_ACTION_ID: ClassVar[str] = "page_selection_action_id"

    CREATE_NEW_PAGE_OPTION_ID: ClassVar[str] = "creat_new_page_option"
    CREATE_NEW_PAGE_OPTION_TEXT: ClassVar[str] = "Create New Page"

    NEW_PAGE_TITLE_LABEL_TEXT: ClassVar[str] = "New Page Title"
    NEW_PAGE_TITLE_BLOCK_ID: ClassVar[str] = "new_page_title_block_id"
    NEW_PAGE_TITLE_ACTION_ID: ClassVar[str] = "new_page_title_action_id"

    SUBMIT_TEXT: ClassVar[str] = "Submit"
    CLOSE_TEXT: ClassVar[str] = "Cancel"

    @staticmethod
    def get_view_title() -> str:
        """
        Helper to fetch Title of Place Documentation modal view.
        """
        return PlaceDocModalView.VIEW_TITLE

    @staticmethod
    def is_create_new_page_action(action: SelectMenuAction) -> bool:
        """
        Returns True if this action represents the Create New Page selection by the user
        and False otherwise.     
        """
        return action.get_selected_option_id() == PlaceDocModalView.CREATE_NEW_PAGE_OPTION_ID

    @staticmethod
    def create_select_option_object(select_option_data: SelectOptionData) -> SelectOptionObject:
        """
        Create Select Option Object from Select Option Data.
        """
        return SelectOptionObject(
            text=TextObject(type=TextObject.TYPE_PLAIN_TEXT,
                            text=select_option_data.text),
            value=select_option_data.id,
        )

    @staticmethod
    def create_page_selection_menu_element(options: List[SelectOptionObject],
                                           selected_option: SelectOptionObject = None) -> SelectMenuStaticElement:
        """
        Create Page Selection Menu Selection Element from given options. If Selected Option is set as the input
        then we set it in the menu as well.
        """
        select_menu_element = SelectMenuStaticElement(
            action_id=PlaceDocModalView.PAGE_SELECTION_ACTION_ID,
            options=options,
        )
        if selected_option:
            select_menu_element.initial_option = selected_option
        return select_menu_element


def place_document_base_view() -> PlaceDocModalView:
    """
    Returns base Modal View to place created section from previous view.
    This is used by other helper methods to add custom Blocks depending the state
    of the view.
    """
    return PlaceDocModalView(
        title=PlainTextObject(text=PlaceDocModalView.VIEW_TITLE),
        blocks=[
            RichTextBlock(
                block_id=PlaceDocModalView.PLACE_DOC_INFO_BLOCK_ID,
                elements=[
                    RichTextSectionElement(
                        elements=[
                            RichTextObject(
                                type=RichTextObject.TYPE_TEXT,
                                text=PlaceDocModalView.PLACE_DOC_INFO_TEXT,
                            )
                        ]
                    ),
                ],
            )
        ],
        submit=PlainTextObject(text=PlaceDocModalView.SUBMIT_TEXT),
        close=PlainTextObject(text=PlaceDocModalView.CLOSE_TEXT),
    )


def place_document_view() -> PlaceDocModalView:
    """
    Returns Modal View that allows user to select which page to place the created section.
    It adds a Selection Menu with options the user can choose from.
    """
    # Create selection Menu from options.
    create_new_page_option = PlaceDocModalView.create_select_option_object(
        PlaceDocModalView.SelectOptionData(
            text=PlaceDocModalView.CREATE_NEW_PAGE_OPTION_TEXT,
            id=PlaceDocModalView.CREATE_NEW_PAGE_OPTION_ID
        )
    )
    select_menu_element = PlaceDocModalView.create_page_selection_menu_element(
        options=[
            create_new_page_option,
            PlaceDocModalView.create_select_option_object(
                PlaceDocModalView.SelectOptionData(text="FAQs", id="xyz_id")
            )
        ]
    )

    # Add selections to base view.
    place_doc_base_view = place_document_base_view()
    selection_input_block = InputBlock(
        label=PlainTextObject(
            text=PlaceDocModalView.PAGE_SELECTION_LABEL_TEXT),
        block_id=PlaceDocModalView.PAGE_SELECTION_BLOCK_ID,
        element=select_menu_element,
        dispatch_action=True,
    )
    place_doc_base_view.blocks.append(selection_input_block)
    return place_doc_base_view


def place_document_with_new_page_title_input() -> PlaceDocModalView:
    """
    Returns Modal View with input to create new page. User can still elect
    to select a different Page option even in this view.
    """
    # Create selection Menu from options.
    create_new_page_option = PlaceDocModalView.create_select_option_object(
        PlaceDocModalView.SelectOptionData(
            text=PlaceDocModalView.CREATE_NEW_PAGE_OPTION_TEXT,
            id=PlaceDocModalView.CREATE_NEW_PAGE_OPTION_ID
        )
    )
    select_menu_element = PlaceDocModalView.create_page_selection_menu_element(
        options=[
            create_new_page_option,
            PlaceDocModalView.create_select_option_object(
                PlaceDocModalView.SelectOptionData(text="FAQs", id="xyz_id")
            )
        ],
        selected_option=create_new_page_option
    )

    # Add selections to base view.
    place_doc_base_view = place_document_base_view()
    selection_input_block = InputBlock(
        label=PlainTextObject(
            text=PlaceDocModalView.PAGE_SELECTION_LABEL_TEXT),
        block_id=PlaceDocModalView.PAGE_SELECTION_BLOCK_ID,
        element=select_menu_element,
        dispatch_action=True,
    )
    place_doc_base_view.blocks.append(selection_input_block)

    # Add New Page title input.
    new_page_title_input_block = InputBlock(
        label=PlainTextObject(
            text=PlaceDocModalView.NEW_PAGE_TITLE_LABEL_TEXT),
        block_id=PlaceDocModalView.NEW_PAGE_TITLE_BLOCK_ID,
        element=PlainTextInputElement(
            action_id=PlaceDocModalView.NEW_PAGE_TITLE_ACTION_ID)
    )
    place_doc_base_view.blocks.append(new_page_title_input_block)

    return place_doc_base_view


def place_document_with_selected_page_option() -> PlaceDocModalView:
    """
    Returns Modal View with selected page as input. User can still elect
    to select a different Page option even in this view.

    TODO: The option is currently hardcoded. Will change in the future to 
    dynamic option.
    """
    # Create selection Menu from options.
    selected_option = PlaceDocModalView.create_select_option_object(
        PlaceDocModalView.SelectOptionData(text="FAQs", id="xyz_id")
    )
    select_menu_element = PlaceDocModalView.create_page_selection_menu_element(
        options=[
            PlaceDocModalView.create_select_option_object(
                PlaceDocModalView.SelectOptionData(
                    text=PlaceDocModalView.CREATE_NEW_PAGE_OPTION_TEXT,
                    id=PlaceDocModalView.CREATE_NEW_PAGE_OPTION_ID
                )
            ),
            selected_option
        ],
        selected_option=selected_option
    )

    # Add selections to base view.
    place_doc_base_view = place_document_base_view()
    selection_input_block = InputBlock(
        label=PlainTextObject(
            text=PlaceDocModalView.PAGE_SELECTION_LABEL_TEXT),
        block_id=PlaceDocModalView.PAGE_SELECTION_BLOCK_ID,
        element=select_menu_element,
        dispatch_action=True,
    )
    place_doc_base_view.blocks.append(selection_input_block)
    return place_doc_base_view


class PlaceDocSubmissionPayload(BaseModel):
    """
    Atttributes in view submission payload when a new section is placed in 
    a page.
    """
    class PlaceDocSubmissionView(BaseModel):
        class PlaceDocSubmissionState(BaseModel):
            values: Dict[str, Dict]
        state: PlaceDocSubmissionState

    view: PlaceDocSubmissionView

    def is_new_page_submission(self) -> bool:
        """
        Returns True if section should be created in new page and False otherwise.
        """
        for value in self.view.state.values:
            if value == PlaceDocModalView.NEW_PAGE_TITLE_BLOCK_ID:
                return True
        return False


class PlaceDocNewPageSubmissionPayload(BaseModel):
    """
    Atttributes in view submission payload when a new section is placed in 
    a New page.
    """
    class PlaceDocNewPageSubmissionView(BaseModel):
        class PlaceDocNewPageState(BaseModel):
            class NewPageValues(BaseModel):
                class PageSelectionBlock(BaseModel):
                    class PageSelectionAction(BaseModel):
                        selected_option: SelectedOptionText
                        type: str

                        @validator("type")
                        def validate_type(cls, v):
                            if v != 'static_select':
                                raise ValueError(
                                    f"Expected static_select element type, got {v}")
                            return v

                    page_selection_action_id: PageSelectionAction

                class NewPageTitleBlock(BaseModel):
                    new_page_title_action_id: InputPlainTextValue

                page_selection_block_id: PageSelectionBlock
                new_page_title_block_id: NewPageTitleBlock
            values: NewPageValues

        state: PlaceDocNewPageState
        id: str

    view: PlaceDocNewPageSubmissionView

    def get_new_page_title(self) -> str:
        """
        Return new page title in plain text format.
        """
        return self.view.state.values.new_page_title_block_id.new_page_title_action_id.get_value()

    def get_view_id(self) -> str:
        """
        Get view ID associated with the payload.        
        """
        return self.view.id
