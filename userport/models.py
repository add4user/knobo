from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Annotated
from datetime import datetime

# Represents an ObjectId field in the database.
# It will be represented as a `str` on the model so that it can be serialized to JSON.
PyObjectId = Annotated[str, "MongoDB Object Id"]


class UserModel(BaseModel):
    """
    Model representing single User stored in the database.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    first_name: str = Field(...)
    last_name: str = Field(...)
    organization: str = Field(...)
    email: str = Field(...)
    password: str = Field(...)
    created: datetime = Field(...)
    last_updated: datetime = Field(...)
    is_authenticated: bool = False
    is_active: bool = False
    email_verified: bool = False
