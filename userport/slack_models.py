from userport.models import PyObjectId
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

"""
Module with Slack App Model defintions.
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
    # Heading of the section to be added in Markdown format.
    # Empty when we are uploading from external doc like web page or Google Docs.
    heading: str = Field(default="")
    # Text associated with section to be added in Markdown format.
    # Empty when we are uploading from external doc like web page or Google Docs.
    text: str = Field(default="")
    # Upload status. 'Not Started' is the default value.
    status: SlackUploadStatus = SlackUploadStatus.NOT_STARTED
    # Error message encountered during upload. Set to empty string by default.
    error_message: str = Field(default="")
    # Time when upload was initiated.
    created_time: Optional[datetime] = None
    # Time when upload was last updated.
    last_updated_time: Optional[datetime] = None


"""
Collection: SlackSections
"""


class SlackSection(BaseModel):
    """
    Representation of a section within a document created or uploaded by a user.
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    # Upload ID of given section.
    upload_id: str
    # Slack Workspace ID that the section is a part of.
    team_id: str = Field(...)
    # ID of the parent section and empty if root section.
    # We store this to reconstruct the page correctly in the UI.
    # The order is determined by DFS starting from the top of the document.
    parent_section_id: str = Field(default="")
    # ID of the previous section in the same document, empty for the first section in the document.
    # The order is determined by DFS over the document starting from the top.
    prev_section_id: str = Field(default="")
    # ID of the next section in the same document, empty for the last section in the document.
    # The order is determined by DFS over the document starting from the top.
    next_section_id: str = Field(default="")
    # URL of the document the section is part of.
    url: str = Field(default="")
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
    # Proper nouns in entire document and is copied to each section (like denormalization)
    # Done to ensure sections from same document have the same score during search.
    proper_nouns_in_doc: List[str] = []
    # ID of the section creator.
    creator_id: str = Field(...)
    # Email of the section creator.
    creator_email: str = Field(...)
    # Time when section was created.
    created_time: Optional[datetime] = None
    # ID of the last person to update the section.
    updater_id: str = Field(...)
    # Email of the last updater of the section.
    updated_email: str = Field(...)
    # Time when section was last updated.
    last_updated_time: Optional[datetime] = None
