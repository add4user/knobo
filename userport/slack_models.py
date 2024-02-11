from userport.models import PyObjectId
from pydantic import BaseModel, Field
from pydantic_core import CoreSchema, core_schema
from typing import Optional, List, Union, Any
from datetime import datetime
from bson.objectid import ObjectId
from enum import Enum

"""
Module with Slack App Model defintions.
"""


# Need to define Custom Pydantic class around 3P Type ObjectId
# to make Dict serialization work.
# Answer take from here: https://stackoverflow.com/posts/77101754/revisions
class CustomPyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Any,
    ) -> CoreSchema:
        def validate(value: str) -> ObjectId:
            if not ObjectId.is_valid(value):
                raise ValueError("Invalid ObjectId")
            return ObjectId(value)

        return core_schema.no_info_plain_validator_function(
            function=validate,
            serialization=core_schema.to_string_ser_schema(),
        )


class BaseFindRequest(BaseModel):
    """
    Base Model for Find Requests in MongoDB.
    """


class BaseUpdateSubRequest(BaseModel):
    """
    Base Model for Update Requests in MongoDB.
    """


"""
Collection: SlackUploads
"""


class SlackUploadStatus(str, Enum):
    """
    We choose strEnum to ensure that serialization/deserialization is
    seamless to the string value and back.
    """
    NOT_STARTED = 'Not Started'
    IN_PROGRESS = 'In Progress'
    COMPLETED = 'Completed'
    FAILED = 'Failed'


class SlackUpload(BaseModel):
    """
    Metadata associated with documentation addition or upload.
    Used to track progress of the upload and store error reasons
    if the upload fails.
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    # Callback ID of associated the Shortcut.
    shortcut_callback_id: str = Field(...)
    # ID of the Modal view that needs to be tracked.
    view_id: str = Field(default="")
    # Response URL of the Slash command that needs to be responded to.
    response_url: str = Field(...)
    # Channel ID whether we received the documentation request from.
    # Set when we use Message Shortcut to create documentation.
    channel_id: str = Field(default="")
    # Message ID whether we received the documentation request from.
    # Set when we use Message Shortcut to create documentation.
    message_ts: str = Field(default="")
    # ID of the uploader.
    creator_id: str = Field(...)
    # Slack Workspace ID that the section is a part of.
    team_id: str = Field(...)
    # Slack Workspace Domain that the section is a part of.
    team_domain: str = Field(...)
    # Heading of the section to be added in Plain text.
    # Empty when we are uploading from external doc like web page or Google Docs.
    heading_plain_text: str = Field(default="")
    # Text associated with section to be added in Markdown format.
    # Empty when we are uploading from external doc like web page or Google Docs.
    text_markdown: str = Field(default="")
    # Upload status. 'Not Started' is the default value.
    status: SlackUploadStatus = SlackUploadStatus.NOT_STARTED
    # Error message encountered during upload. Set to empty string by default.
    error_message: str = Field(default="")
    # Time when upload was initiated.
    created_time: Optional[datetime] = None
    # Time when upload was last updated.
    last_updated_time: Optional[datetime] = None


class FindSlackUploadRequest(BaseFindRequest):
    """
    Model to ensure fetch filters for SlackUpload are less error
    prone when calling MongoDB.

    Please ensure that attributes here are in sync with
    SlackUpload attributes.
    """
    view_id: Optional[str] = None
    id: Optional[CustomPyObjectId] = Field(
        serialization_alias="_id", default=None)


class UpdateSlackUploadRequest(BaseUpdateSubRequest):
    """
    Model to ensure updates to fields of SlackUpload are less
    error prone when writing to MongoDB.

    Please ensure that attributes here are in sync with
    SlackUpload attributes.
    """
    heading_plain_text: Optional[str] = None
    text_markdown: Optional[str] = None
    status: Optional[SlackUploadStatus] = None
    last_updated_time: Optional[datetime] = None


"""
Collection: SlackSections
"""


class SlackSection(BaseModel):
    """
    Representation of a section within a page created or uploaded by a user.

    Whenever an attribute is updated here, please check if it needs to be updated
    in UpdateSlackSection as well.
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    # Upload ID associated with the  given section.
    upload_id: str = Field(default="")
    # Slack Workspace ID that the section is a part of.
    team_id: str = Field(default="")
    # Slack Workspace Domain that the section is a part of.
    team_domain: str = Field(default="")
    # ID of the page the section is part of.
    page_id: str = Field(default="")
    # HTML Section ID. This is used to generate a URL to this section directly.
    html_section_id: str = Field(default="")
    # HTML ID of the page that this section is part of. This is
    # used to construct URL to this section without needing to
    # query the page section each time.
    page_html_section_id: str = Field(default="")
    # ID of the parent section and empty if root section of the page.
    # We store this to reconstruct the page correctly in the UI.
    # The order is determined by DFS starting from the top of the page.
    parent_section_id: str = Field(default="")
    # Ordered child section IDs associatd with given section. Empty if there are no child sections.
    # The ordering of section IDs is top-down i.e. earlier section IDs are above follwing sections in the page.
    child_section_ids: List[str] = []
    # Heading of the section in Markdown format.
    heading: str = Field(default="")
    # Text associated with section in Markdown format.
    text: str = Field(default="")
    # Detailed summary of given section.
    summary: str = Field(default="")
    # Context from preceding sections used to generate summary of section text.
    prev_sections_context: str = Field(default="")
    # Vector Embedding of the detailed summary.
    summary_vector_embedding: List[float] = []
    # Proper nouns found in this section.
    proper_nouns_in_section: List[str] = []
    # Proper nouns in entire page and is copied to each section (like denormalization)
    # Done to ensure sections from same page have the same score during search.
    proper_nouns_in_doc: List[str] = []
    # ID of the section creator.
    creator_id: str = Field(default="")
    # Email of the section creator.
    creator_email: str = Field(default="")
    # Time when section was created.
    created_time: Optional[datetime] = None
    # ID of the last person to update the section.
    updater_id: str = Field(default="")
    # Email of the last updater of the section.
    updater_email: str = Field(default="")
    # Time when section was last updated.
    last_updated_time: Optional[datetime] = None


class FindSlackSectionRequest(BaseFindRequest):
    """
    Model to ensure fetch filters for SlackSection are less error
    prone when calling MongoDB.

    Please ensure that attributes here are in sync with
    SlackSection attributes.
    """
    id: Optional[CustomPyObjectId] = Field(
        serialization_alias="_id", default=None)
    team_domain: Optional[str] = None
    html_section_id: Optional[str] = None
    page_id: Optional[str] = None
    parent_section_id: Optional[str] = None


class UpdateSlackSectionRequest(BaseUpdateSubRequest):
    """
    Model to ensure updates to fields of SlackSection are less
    error prone when writing to MongoDB.

    Please ensure that attributes here are in sync with
    SlackSection attributes.
    """
    parent_section_id: Optional[str] = None
    child_section_ids: Optional[List[str]] = None
    page_id: Optional[str] = None
    summary: Optional[str] = None
    prev_sections_context: Optional[str] = None
    summary_vector_embedding: Optional[List[float]] = None
    proper_nouns_in_section: Optional[List[str]] = None
    proper_nouns_in_doc: Optional[List[str]] = None
    updater_id: str = Field(default="")
    updater_email: str = Field(default="")
    child_section_ids: Optional[List[str]] = None
    last_updated_time: Optional[datetime] = None
    heading: Optional[str] = None
    text: Optional[str] = None


class FindAndUpateSlackSectionRequest(BaseModel):
    """
    Wrapper class to find and update slack section.
    """
    find_request: FindSlackSectionRequest
    update_request: UpdateSlackSectionRequest


class VectorSearchSlackSectionResult(BaseModel):
    """
    Result of vector search over SlackSections. All attributes except 
    'score' are attributes common to SlackSection.
    """
    # ID of the section. To get other fields of the section, we can just
    # do another read during analysis to pull that information.
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    # Markdown formatted heading of the section.
    heading: str = Field(...)
    # Markdown formatted text associated with the section.
    text: str = Field(...)
    # Slack Workspace Domain that the section is a part of.
    team_domain: str = Field(...)
    # HTML section ID of page that section residers under (needed for URL construction).
    page_html_section_id: str = Field(...)
    # HTML section ID of section (needed for URL construction).
    html_section_id: str = Field(...)
    # Document score associated with search query (stored in parent model).
    score: float = Field(...)


class BaseUpdateRequest(BaseModel):
    """
    General update request format to MongoDB. This model
    will be converted to Python dictionary before being
    sent to MongoDB for the update.
    """
    update_sub_request: Union[UpdateSlackUploadRequest, UpdateSlackSectionRequest] = Field(
        serialization_alias="$set")
