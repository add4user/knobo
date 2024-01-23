from typing import Dict
from pydantic import BaseModel

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
    """
    class Values(BaseModel):
        class HeadingBlock(BaseModel):
            create_doc_heading_value: Dict

        class BodyBlock(BaseModel):
            create_doc_body_value: Dict

        create_doc_heading: HeadingBlock
        create_doc_body: BodyBlock

    values: Values


class CreateDocSubmissionView(CommonView):
    """
    Create Document View submission.
    """
    state: CreateDocState


class CreateDocSubmissionPayload(InteractionPayload):
    """
    Class containing fields we care about in Create Document View submission payload.
    """
    view: CreateDocSubmissionView

    def get_title(self) -> str:
        return self.view.get_title()


class CreateDocModalView:
    """
    Helper methods to manage Create Documentation Modal View.
    """
    VIEW_TITLE = "Create Documentation"

    HEADING_BLOCK_ID = "create_doc_heading"
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
                        "type": "plain_text_input",
                        "action_id": CreateDocModalView.HEADING_ELEMENT_ACTION_ID,
                    }
                },
                {
                    "type": "input",
                    "block_id": CreateDocModalView.BODY_BLOCK_ID,
                    "label": {
                        "type": "plain_text",
                        "text": "Body",
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
