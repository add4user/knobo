from typing import Dict, ClassVar
from pydantic import BaseModel, validator
from userport.slack_blocks import RichTextBlock

"""
Module contains helper classes to manage creation and parsing of Slack Modal Views.

Reference: https://api.slack.com/reference/interaction-payloads/views#view_submission_fields
"""


class InteractionPayload(BaseModel):
    """
    Common class for Block Action, View submission or View Cancel payloads.

    Reference: https://api.slack.com/surfaces/modals#interactions
    """
    type: str

    def is_view_interaction(self) -> bool:
        return self.type.startswith("view")

    def is_view_closed(self) -> bool:
        return self.type == "view_closed"

    def is_view_submission(self) -> bool:
        return self.type == "view_submission"


class CommonView(BaseModel):
    """
    Common class for View objects.

    Reference: https://api.slack.com/reference/surfaces/views
    """
    class Title(BaseModel):
        text: str

    id: str
    title: Title

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
    Create Document View submission.
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
    Class containing fields we care about in Create Document View submission payload.
    """
    class SlackTeam(BaseModel):
        id: str

    class SlackUser(BaseModel):
        id: str

    view: CreateDocSubmissionView
    team: SlackTeam
    user: SlackUser

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


class CreateDocModalView:
    """
    Helper methods to manage Create Documentation Modal View.
    """
    VIEW_TITLE = "Create Documentation"

    HEADING_BLOCK_ID = "create_doc_heading"
    HEADING_INPUT_TYPE = "plain_text_input"
    HEADING_ELEMENT_ACTION_ID = "create_doc_heading_value"
    HEADING_INPUT_TYPE = "plain_text_input"

    BODY_BLOCK_ID = "create_doc_body"
    BODY_ELEMENT_ACTION_ID = "create_doc_body_value"

    @staticmethod
    def create_view() -> Dict:
        """
        Creates Modal View from given Slash command Trigger ID and returns a Slack View object.
        View: https://api.slack.com/reference/surfaces/views#modal__modal-view-example
        """
        return {
            "type": "modal",
            "title": {
                "type": "plain_text",
                "text": CreateDocModalView.get_create_doc_view_title(),
                "emoji": True
            },
            "blocks": [
                {
                    "type": "input",
                    "block_id": CreateDocModalView.HEADING_BLOCK_ID,
                    "label": {
                        "type": "plain_text",
                        "text": "Heading",
                        "emoji": True
                    },
                    "element": {
                        "type": CreateDocModalView.HEADING_INPUT_TYPE,
                        "action_id": CreateDocModalView.HEADING_ELEMENT_ACTION_ID,
                    }
                },
                {
                    "type": "input",
                    "block_id": CreateDocModalView.BODY_BLOCK_ID,
                    "label": {
                        "type": "plain_text",
                        "text": "Content",
                        "emoji": True
                    },
                    "element": {
                        "type": "rich_text_input",
                        "action_id": CreateDocModalView.BODY_ELEMENT_ACTION_ID,
                    }
                }
            ],
            "submit": {
                "type": "plain_text",
                "text": "Submit",
                "emoji": True
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel"
            },
            "notify_on_close": True,
        }

    @staticmethod
    def get_create_doc_view_title() -> str:
        """
        Helper to fetch Title of Create Documentation modal view.
        """
        return CreateDocModalView.VIEW_TITLE
