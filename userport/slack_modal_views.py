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
    RichTextListElement,
    SelectMenuStaticElement,
    SelectOptionObject,
    HeaderBlock,
    DividerBlock
)
from userport.slack_models import SlackSection
from userport.utils import get_heading_content, get_heading_level_and_content
import userport.db

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
        domain: str

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
        return len(self.actions) > 0 and self.actions[0].action_id == PlaceDocViewFactory.PAGE_SELECTION_ACTION_ID


class SelectMenuAction(BaseModel):
    """
    Class containing Select Menu Action attributes.
    Associated with SelectMenuBlockActionsPayload defined below.
    """
    type: str
    action_id: str
    block_id: str
    selected_option: SelectOptionObject

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

    def get_selected_option(self) -> SelectOptionObject:
        """
        Returns selected option.
        """
        return self.selected_option


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

    def get_team_domain(self) -> str:
        return self.team.domain


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

    def get_team_domain(self) -> str:
        """
        Return domain of the Slack Workspace.
        """
        return self.team.domain

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

    def get_team_domain(self) -> str:
        """
        Return Domain of the Slack Workspace.
        """
        return self.team.domain

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


class CreateDocViewFactory:
    """
    Class that takes creates a view to ask for section heading and 
    content inputs from a user.
    """
    VIEW_TITLE = "Create Section"

    INFORMATION_BLOCK_ID = "create_doc_info"
    INFORMATION_TEXT = "You are about to create a new section with a heading and associated body that will be added to the documentation." + \
        " Once both fields are filled, please click Next. You can abort this operation by clicking Cancel."

    HEADING_TEXT = "Heading"
    HEADING_BLOCK_ID = "create_doc_heading"
    HEADING_ELEMENT_ACTION_ID = "create_doc_heading_value"

    BODY_TEXT = "Body"
    BODY_BLOCK_ID = "create_doc_body"
    BODY_ELEMENT_ACTION_ID = "create_doc_body_value"

    SUBMIT_TEXT = "Next"
    CLOSE_TEXT = "Cancel"

    @staticmethod
    def get_view_title() -> str:
        """
        Helper to fetch Title of Create Documentation modal view.
        """
        return CreateDocViewFactory.VIEW_TITLE

    def create_view(self, initial_body_value: RichTextBlock) -> BaseModalView:
        """
        Returns view to Create document with given initial value for section body.
        """
        return BaseModalView(
            title=PlainTextObject(text=CreateDocViewFactory.get_view_title()),
            blocks=[
                RichTextBlock(
                    block_id=self.INFORMATION_BLOCK_ID,
                    elements=[
                        RichTextSectionElement(
                            elements=[
                                RichTextObject(
                                    type=RichTextObject.TYPE_TEXT,
                                    text=self.INFORMATION_TEXT,
                                )
                            ]
                        )
                    ],
                ),
                InputBlock(
                    label=PlainTextObject(
                        text=self.HEADING_TEXT),
                    block_id=self.HEADING_BLOCK_ID,
                    element=PlainTextInputElement(
                        action_id=self.HEADING_ELEMENT_ACTION_ID)
                ),
                InputBlock(
                    label=PlainTextObject(text=self.BODY_TEXT),
                    block_id=self.BODY_BLOCK_ID,
                    element=RichTextInputElement(
                        action_id=self.BODY_ELEMENT_ACTION_ID,
                        initial_value=initial_body_value,
                    )
                )
            ],
            submit=PlainTextObject(text=self.SUBMIT_TEXT),
            close=PlainTextObject(text=self.CLOSE_TEXT),
        )


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
            if value == PlaceDocViewFactory.NEW_PAGE_TITLE_BLOCK_ID:
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
                        selected_option: SelectOptionObject
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


class PlaceDocViewFactory:
    """
    Factory class to help create instances of PlaceDocModalView.
    """
    VIEW_TITLE = "Select Location"

    PLACE_DOC_INFO_BLOCK_ID = "place_doc_info_block_id"
    PLACE_DOC_INFO_TEXT = "Please select the Page where you want to add this section or create a new page for it.\n"
    PAGE_SELECTION_LABEL_TEXT = "Select Page"
    PAGE_SELECTION_BLOCK_ID = "page_selection_block_id"
    PAGE_SELECTION_ACTION_ID = "page_selection_action_id"

    CREATE_NEW_PAGE_OPTION_ID = "creat_new_page_option"
    CREATE_NEW_PAGE_OPTION_TEXT = "Create New Page"

    PROMPT_USER_ABOUT_NEW_PAGE_TITLE_BLOCK_ID = "new_page_title_info_block_id"
    PROMPT_USER_ABOUT_NEW_PAGE_TITLE = "Please provide a Title for the new page as well."

    NEW_PAGE_TITLE_LABEL_TEXT = "New Page Title"
    NEW_PAGE_TITLE_BLOCK_ID = "new_page_title_block_id"
    NEW_PAGE_TITLE_ACTION_ID = "new_page_title_action_id"

    PAGE_LAYOUT_HEADER_TEXT = "Page Layout"
    ALL_SECTIONS_IN_PAGE_BLOCK_ID = "all_sections_in_page_block_id"

    PROMPT_USER_TO_SELECT_PARENT_SECTION_BLOCK_ID = "parent_section_selection_block_id"
    PROMPT_USER_TO_SELECT_PARENT_SECTION_TEXT = "Please select the parent section directly under which the new section will be placed."

    PARENT_SECTION_SELECTION_BLOCK_ID = "parent_section_block_id"
    PARENT_SECTION_SELECTION_TEXT = "Parent Section"

    SUBMIT_TEXT = "Submit"
    CLOSE_TEXT = "Cancel"

    def create_with_page_options(self, pages_within_team: List[SlackSection]) -> BaseModalView:
        """
        Returns Modal View that allows user to select which page to place the created section.
        It adds a Selection Menu with options the user can choose from.
        """
        base_view = self._create_base_view()

        # Create Page selection Menu and add to view.
        select_menu_element: SelectMenuStaticElement = self._create_selection_menu_from_slack_pages(
            pages_within_team=pages_within_team)
        page_selection_input_block = self._create_selection_menu_input_block(
            block_id=self.PAGE_SELECTION_BLOCK_ID,
            text=self.PAGE_SELECTION_LABEL_TEXT,
            select_menu_element=select_menu_element
        )
        base_view.blocks.append(page_selection_input_block)

        return base_view

    def create_with_new_page_option_selected(self, pages_within_team: List[SlackSection]) -> BaseModalView:
        """
        Create Modal view with new page option selected by user. This is the view that
        results from selection in create_with_page_options view.
        """
        base_view = self._create_base_view()

        # Create Page selection Menu (with create new page as selected option) and add to view.
        create_new_page_option = self._create_select_option_object(
            text=self.CREATE_NEW_PAGE_OPTION_TEXT,
            id=self.CREATE_NEW_PAGE_OPTION_ID
        )
        select_menu_element: SelectMenuStaticElement = self._create_selection_menu_from_slack_pages(
            pages_within_team=pages_within_team, selected_option=create_new_page_option)
        page_selection_input_block = self._create_selection_menu_input_block(
            block_id=self.PAGE_SELECTION_BLOCK_ID,
            text=self.PAGE_SELECTION_LABEL_TEXT,
            select_menu_element=select_menu_element
        )
        base_view.blocks.append(page_selection_input_block)

        base_view.blocks.append(DividerBlock())

        # Provide info to user that they need to provide page title as well.
        new_page_title_info = self._create_rich_text_block(
            block_id=self.PROMPT_USER_ABOUT_NEW_PAGE_TITLE_BLOCK_ID, text=self.PROMPT_USER_ABOUT_NEW_PAGE_TITLE)
        base_view.blocks.append(new_page_title_info)

        # Create New Page title input block and add to base view.
        new_page_title_input_block = self._create_new_page_title_input_block()
        base_view.blocks.append(new_page_title_input_block)

        return base_view

    def create_with_selected_page(self, pages_within_team: List[SlackSection], selected_option: SelectOptionObject) -> BaseModalView:
        """
        Create Modal View with existing page selected by user.
        """
        base_view = self._create_base_view()

        # Create Page selection Menu (with selected page as selected option) and add to view.
        select_menu_element: SelectMenuStaticElement = self._create_selection_menu_from_slack_pages(
            pages_within_team=pages_within_team, selected_option=selected_option
        )
        page_selection_input_block = self._create_selection_menu_input_block(
            block_id=self.PAGE_SELECTION_BLOCK_ID,
            text=self.PAGE_SELECTION_LABEL_TEXT,
            select_menu_element=select_menu_element
        )
        base_view.blocks.append(page_selection_input_block)

        base_view.blocks.append(DividerBlock())

        # Add header block for page layout.
        header_block = HeaderBlock(text=TextObject(
            type=TextObject.TYPE_PLAIN_TEXT, text=self.PAGE_LAYOUT_HEADER_TEXT))
        base_view.blocks.append(header_block)

        # Fetch all sections from selected page and display page layout in rich text block.
        page_section: SlackSection = None
        try:
            page_section = next(filter(lambda x: str(
                x.id) == selected_option.value, pages_within_team))
        except StopIteration as e:
            raise ValueError(
                f'Failed to find selected option: {selected_option} within Slack page sections: {pages_within_team} with error: {e}')
        ordered_sections_in_page = userport.db.get_ordered_slack_sections_in_page(
            team_domain=page_section.team_domain, page_html_section_id=page_section.html_section_id)
        ordered_section_block: RichTextBlock = self._get_ordered_sections_display(
            ordered_sections_in_page=ordered_sections_in_page)
        base_view.blocks.append(ordered_section_block)

        # Prompt user to select parent Section under which to place the new section.
        select_parent_section_info = self._create_rich_text_block(
            block_id=self.PROMPT_USER_TO_SELECT_PARENT_SECTION_BLOCK_ID, text=self.PROMPT_USER_TO_SELECT_PARENT_SECTION_TEXT)
        base_view.blocks.append(select_parent_section_info)

        # Add Selection Menu for all parent sections (basically all current sections) in the page.
        parent_selection_menu = self._create_selection_menu_from_sections(
            slack_sections=ordered_sections_in_page)
        parent_section_input_block = self._create_selection_menu_input_block(
            block_id=self.PARENT_SECTION_SELECTION_BLOCK_ID,
            text=self.PARENT_SECTION_SELECTION_TEXT,
            select_menu_element=parent_selection_menu,
        )
        base_view.blocks.append(parent_section_input_block)

        return base_view

    @staticmethod
    def is_create_new_page_action(action: SelectMenuAction) -> bool:
        """
        Returns True if this action represents the Create New Page selection by the user
        and False otherwise.     
        """
        return action.get_selected_option_id() == PlaceDocViewFactory.CREATE_NEW_PAGE_OPTION_ID

    @staticmethod
    def get_view_title() -> str:
        """
        Helper to fetch Title of Place Documentation modal view.
        """
        return PlaceDocViewFactory.VIEW_TITLE

    def _get_ordered_sections_display(self, ordered_sections_in_page: List[SlackSection]) -> RichTextBlock:
        """
        Return a RichTextBlock displaying ordered sections in a page.
        """
        all_lists: List[RichTextListElement] = []
        cur_list: RichTextListElement = None
        for section in ordered_sections_in_page:
            heading_level, heading_content = get_heading_level_and_content(
                markdown_text=section.heading)
            indent: int = heading_level - 1
            if not cur_list or cur_list.indent != indent:
                if cur_list:
                    all_lists.append(cur_list)
                # Create a new list.
                cur_list = RichTextListElement(
                    style=RichTextListElement.STYLE_BULLET,
                    indent=indent,
                    elements=[
                        RichTextSectionElement(elements=[
                            RichTextObject(
                                type=RichTextObject.TYPE_TEXT, text=heading_content)
                        ])
                    ]
                )
            else:
                # Append to current list.
                cur_list.elements.append(
                    RichTextSectionElement(elements=[
                        RichTextObject(
                            type=RichTextObject.TYPE_TEXT, text=heading_content)
                    ])
                )
        if cur_list:
            all_lists.append(cur_list)

        return RichTextBlock(block_id=self.ALL_SECTIONS_IN_PAGE_BLOCK_ID, elements=all_lists)

    def _create_selection_menu_from_slack_pages(self, pages_within_team: List[SlackSection], selected_option: SelectOptionObject = None) -> SelectMenuStaticElement:
        """
        Helper to create selection menu from given slack page sections.
        """
        all_options: List[SelectOptionObject] = []

        create_new_page_option = self._create_select_option_object(
            text=self.CREATE_NEW_PAGE_OPTION_TEXT,
            id=self.CREATE_NEW_PAGE_OPTION_ID
        )
        all_options.append(create_new_page_option)

        for page in pages_within_team:
            page_option = self._create_select_option_object(
                text=get_heading_content(markdown_text=page.heading),
                id=str(page.id)
            )
            all_options.append(page_option)
        return self._create_selection_menu_element(
            options=all_options, selected_option=selected_option)

    def _create_selection_menu_from_sections(self, slack_sections: List[SlackSection]) -> SelectMenuStaticElement:
        """
        Create and return selection menu with given slack sections as options.
        """
        all_options: List[SelectOptionObject] = []
        for section in slack_sections:
            heading_content = get_heading_content(section.heading)
            selection_option = self._create_select_option_object(
                text=heading_content, id=str(section.id))
            all_options.append(selection_option)
        return self._create_selection_menu_element(options=all_options)

    def _create_select_option_object(self, text: str, id: str) -> SelectOptionObject:
        """
        Helper to create SelectOptionObject from given text and ID.
        """
        return SelectOptionObject(
            text=TextObject(type=TextObject.TYPE_PLAIN_TEXT, text=text),
            value=id,
        )

    def _create_selection_menu_element(self, options: List[SelectOptionObject],
                                       selected_option: SelectOptionObject = None) -> SelectMenuStaticElement:
        """
        Create Selection Menu Selection Element from given options. If Selected Option is set as the input
        then we set it in the menu as well.
        """
        select_menu_element = SelectMenuStaticElement(
            action_id=self.PAGE_SELECTION_ACTION_ID,
            options=options,
        )
        if selected_option:
            select_menu_element.initial_option = selected_option
        return select_menu_element

    def _create_selection_menu_input_block(self, block_id: str, text: str, select_menu_element: SelectMenuStaticElement) -> InputBlock:
        """
        Helper to create input block that contains page selection menu.
        """
        return InputBlock(
            label=PlainTextObject(text=text),
            block_id=block_id,
            element=select_menu_element,
            dispatch_action=True,
        )

    def _create_new_page_title_input_block(self) -> InputBlock:
        """
        Helper to create input block that contains new page title.
        """
        return InputBlock(
            label=PlainTextObject(
                text=self.NEW_PAGE_TITLE_LABEL_TEXT),
            block_id=self.NEW_PAGE_TITLE_BLOCK_ID,
            element=PlainTextInputElement(
                action_id=self.NEW_PAGE_TITLE_ACTION_ID)
        )

    def _create_rich_text_block(self, block_id: str, text: str) -> RichTextBlock:
        """
        Helper to create rich text block.
        """
        return RichTextBlock(
            block_id=block_id,
            elements=[
                RichTextSectionElement(
                    elements=[
                        RichTextObject(
                            type=RichTextObject.TYPE_TEXT, text=text)
                    ]
                ),
            ],
        )

    def _create_base_view(self) -> BaseModalView:
        """
        Returns Base Modal View to place created section from previous view.
        This is used by other helper methods to add custom Blocks depending the state
        of the view.

        This view is like the base layout of the place document view.
        """
        return BaseModalView(
            title=PlainTextObject(text=self.VIEW_TITLE),
            blocks=[
                RichTextBlock(
                    block_id=self.PLACE_DOC_INFO_BLOCK_ID,
                    elements=[
                        RichTextSectionElement(
                            elements=[
                                RichTextObject(
                                    type=RichTextObject.TYPE_TEXT,
                                    text=self.PLACE_DOC_INFO_TEXT,
                                )
                            ]
                        ),
                    ],
                )
            ],
            submit=PlainTextObject(text=self.SUBMIT_TEXT),
            close=PlainTextObject(text=self.CLOSE_TEXT),
        )
