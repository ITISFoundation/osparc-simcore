from typing import TypedDict

from aiopg.sa.result import RowProxy

from .exceptions import UserInsufficientRightsError

_GROUPS_SCHEMA_TO_DB = {
    "gid": "gid",
    "label": "name",
    "description": "description",
    "thumbnail": "thumbnail",
    "accessRights": "access_rights",
    "inclusionRules": "inclusion_rules",
}


class AccessRightsDict(TypedDict):
    read: bool
    write: bool
    delete: bool


def check_group_permissions(
    group: RowProxy, user_id: int, gid: int, permission: str
) -> None:
    if not group.access_rights[permission]:
        raise UserInsufficientRightsError(
            user_id=user_id, gid=gid, permission=permission
        )


def convert_groups_db_to_schema(
    db_row: RowProxy, *, prefix: str | None = "", **kwargs
) -> dict:
    converted_dict = {
        k: db_row[f"{prefix}{v}"]
        for k, v in _GROUPS_SCHEMA_TO_DB.items()
        if f"{prefix}{v}" in db_row
    }
    converted_dict.update(**kwargs)
    return converted_dict


def convert_groups_schema_to_db(schema: dict) -> dict:
    return {
        v: schema[k]
        for k, v in _GROUPS_SCHEMA_TO_DB.items()
        if k in schema and k != "gid"
    }
