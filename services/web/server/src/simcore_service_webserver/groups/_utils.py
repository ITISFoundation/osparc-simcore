_GROUPS_SCHEMA_TO_DB = {
    "gid": "gid",
    "label": "name",
    "description": "description",
    "thumbnail": "thumbnail",
    "accessRights": "access_rights",
    "inclusionRules": "inclusion_rules",
}


def convert_groups_schema_to_db(schema: dict) -> dict:
    return {
        v: schema[k]
        for k, v in _GROUPS_SCHEMA_TO_DB.items()
        if k in schema and k != "gid"
    }
