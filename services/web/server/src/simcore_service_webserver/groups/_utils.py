from aiopg.sa.result import RowProxy

_GROUPS_SCHEMA_TO_DB = {
    "gid": "gid",
    "label": "name",
    "description": "description",
    "thumbnail": "thumbnail",
    "accessRights": "access_rights",
    "inclusionRules": "inclusion_rules",
}


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
