from typing import Annotated, Any, NamedTuple, Self, TypedDict

from models_library.api_schemas_webserver.users import MyProfileRestPatch
from models_library.basic_types import IDStr
from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class FullNameDict(TypedDict):
    first_name: str | None
    last_name: str | None


class UserDisplayAndIdNamesTuple(NamedTuple):
    name: str
    email: EmailStr
    first_name: IDStr
    last_name: IDStr

    @property
    def full_name(self) -> IDStr:
        return IDStr.concatenate(self.first_name, self.last_name)


class UserIdNamesTuple(NamedTuple):
    name: str
    email: str


#
# DB models
#


def flatten_dict(d: dict, parent_key="", sep="_"):
    items = []
    for key, value in d.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            # Recursively process nested dictionaries
            items.extend(flatten_dict(value, new_key, sep=sep).items())
        else:
            items.append((new_key, value))
    return dict(items)


class UserModelAdapter(BaseModel):
    """
    Maps ProfileUpdate api schema into UserUpdate db-model
    """

    # NOTE: field names are UserDB columns
    # NOTE: aliases are ProfileUpdate field names

    name: Annotated[str | None, Field(alias="user_name")] = None
    first_name: str | None = None
    last_name: str | None = None

    privacy_hide_username: bool | None = None
    privacy_hide_fullname: bool | None = None
    privacy_hide_email: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def from_rest_schema_model(cls, profile_update: MyProfileRestPatch) -> Self:
        # The mapping of embed fields to flatten keys is done here
        return cls.model_validate(
            flatten_dict(profile_update.model_dump(exclude_unset=True, by_alias=False))
        )

    def to_db_values(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True, by_alias=False)


class UserCredentialsTuple(NamedTuple):
    email: LowerCaseEmailStr
    password_hash: str
    display_name: str
