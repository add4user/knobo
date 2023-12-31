from pydantic import BaseModel, Field, ConfigDict
from pydantic.functional_validators import BeforeValidator
from typing import Optional, Annotated, List
from datetime import datetime
from enum import Enum

# Represents an ObjectId field in the database.
# It will be represented as a `str` on the model so that it can be serialized to JSON.
# The Before validator will convert ObjectId from DB into string so model validation does not
# throw an error.
PyObjectId = Annotated[str, BeforeValidator(str)]


class UploadStatus(str, Enum):
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETE = 'COMPLETE'
    FAILED = 'FAILED'


"""
Collection: Uploads
"""


class UploadModel(BaseModel):
    """
    Represents metadata for a URL of file uploaded by user.
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    # ID of the uploader.
    creator_id: str = Field(...)
    # Time when upload was initiated.
    created: Optional[datetime] = None
    # Domain of the org which should be globally unique.
    org_domain: str = Field(...)
    # URL of the document uploaded.
    url: str = Field(default="")
    # Upload status. By default it is in progress.
    status: UploadStatus = UploadStatus.IN_PROGRESS
    # Error message encountered during upload. Set to empty string by default.
    error_message: str = Field(default="")


"""
Collection: Sections
"""


class SectionModel(BaseModel):
    """
    Representation of a section within a page or document uploaded by the user.
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    # Upload ID of given section.
    upload_id: str
    # Domain of the org which should be globally unique.
    org_domain: str = Field(...)
    # ID of the parent section and empty if root section.
    parent_section_id: str = Field(default="")
    # URL of the document the section is part of.
    url: str = Field(default="")
    # Text associated with section.
    # It includes the title since we don't know if title is needed separately.
    text: str = Field(default="")
    # Detailed summary of given section.
    summary: str = Field(default="")
    # Context from preceding sections used to generate summary of section text
    prev_sections_context: str = Field(default="")
    # Vector Embedding of the detailed summary.
    summary_vector_embedding: List[float] = []
    # Proper nouns found in this section.
    proper_nouns_in_section: str = Field(default="")
    # Proper nouns in entire document and is copied to each section (like denormalization)
    # Done to ensure sections from same document have the same score during search.
    proper_nouns_in_doc: str = Field(default="")
    # ID of the uploader.
    creator_id: str = Field(...)
    # Time when section was written to database.
    created: Optional[datetime] = None


"""
Collection: APIKeys
"""


class APIKeyModel(BaseModel):
    """
    Representation of API key stored in the database as a collection.
    """
    # API key value, it is a hashed value.
    id: Optional[PyObjectId] = Field(serialization_alias="_id")
    # Key prefix to help user manually match key to any key they may hold.
    key_prefix: str = Field(...)
    # Domain of the org which should be globally unique.
    org_domain: str = Field(...)
    # ID of the creator.
    creator_id: str = Field(...)
    # Time when API Key was written to database.
    created: Optional[datetime] = None


"""
Collection: Organizations
"""


class OrganizationModel(BaseModel):
    """
    Model representing an organization. This will be stored as a nested model.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str = Field(...)
    domain: str = Field(...)
    active: bool = True
    created: Optional[datetime] = None
    last_updated: Optional[datetime] = None


"""
Collection: Users
"""


class UserModel(BaseModel):
    """
    Model representing single User stored in the database.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    first_name: str = Field(...)
    last_name: str = Field(...)
    email: str = Field(...)
    password: str = Field(...)
    org_domain: str = Field(...)
    created: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    active: bool = True
    email_verified: bool = False
    is_admin: bool = True

    """
    Need to implement the following helper methods to ensure
    Flask-login works as expected. Except for get_id and is_active other fields
    are not used in determining authentication state of user based on testing.
    """

    def get_id(self) -> str:
        return str(self.id)

    def is_active(self) -> bool:
        return self.active

    def is_authenticated(self) -> bool:
        return False

    def is_anonymous(self) -> bool:
        return False
