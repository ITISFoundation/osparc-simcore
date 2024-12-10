from typing import Annotated, Any, Self

from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, ConfigDict, Field

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


class ToUserUpdateDB(BaseModel):
    """
    Maps ProfileUpdate api-model into UserUpdate db-model
    """

    # NOTE: field names are UserDB columns
    # NOTE: aliases are ProfileUpdate field names

    name: Annotated[str | None, Field(alias="user_name")] = None
    first_name: str | None = None
    last_name: str | None = None

    privacy_hide_fullname: bool | None = None
    privacy_hide_email: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def from_api(cls, profile_update) -> Self:
        # TODO: move this to schema!!!
        # The mapping of embed fields to flatten keys is done here
        return cls.model_validate(
            flatten_dict(profile_update.model_dump(exclude_unset=True, by_alias=False))
        )

    def to_db(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True, by_alias=False)


class UserCredentialsTuple(NamedTuple):
    email: LowerCaseEmailStr
    password_hash: str
    display_name: str
