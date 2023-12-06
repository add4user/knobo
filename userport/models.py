from pydantic import BaseModel, Field, ConfigDict
from pydantic.functional_validators import BeforeValidator
from typing import Optional, Annotated, List
from datetime import datetime

# Represents an ObjectId field in the database.
# It will be represented as a `str` on the model so that it can be serialized to JSON.
# The Before validator will convert ObjectId from DB into string so model validation does not
# throw an error.
PyObjectId = Annotated[str, BeforeValidator(str)]


"""
Collection: APIKeys
"""


class APIKeyModel(BaseModel):
    """
    Representation of API key stored in the database as a collection.
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str = Field(...)
    prefix: str = Field(...)
    value: str = Field(...)
    org_domain: str = Field(...)
    creator_id: str = Field(...)
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
