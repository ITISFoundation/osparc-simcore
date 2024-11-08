import models_library.groups
import simcore_postgres_database.models.groups
from models_library.api_schemas_webserver.groups import GroupGet
from models_library.utils.enums import enum_to_dict


def test_models_library_and_postgress_database_enums_are_equivalent():
    # For the moment these two libraries they do not have a common library to share these
    # basic types so we test here that they are in sync

    assert enum_to_dict(
        simcore_postgres_database.models.groups.GroupType
    ) == enum_to_dict(models_library.groups.GroupTypeInModel)


def test_sanitize_legacy_data():
    users_group_1 = GroupGet.model_validate(
        {
            "gid": "27",
            "label": "A user",
            "description": "A very special user",
            "thumbnail": "",  # <--- empty strings
            "accessRights": {"read": True, "write": False, "delete": False},
        }
    )

    assert users_group_1.thumbnail is None

    users_group_2 = GroupGet.model_validate(
        {
            "gid": "27",
            "label": "A user",
            "description": "A very special user",
            "thumbnail": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAPgAAADMCAMAAABp5J",  # <--- encoded thumbnail are discarded
            "accessRights": {"read": True, "write": False, "delete": False},
        }
    )

    assert users_group_2.thumbnail is None

    assert users_group_1 == users_group_2
