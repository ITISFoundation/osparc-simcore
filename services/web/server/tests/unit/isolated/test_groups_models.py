import enum
from pprint import pformat
from typing import Any

import models_library.groups
import pytest
import simcore_postgres_database.models.groups
from models_library.generics import Envelope
from pydantic import BaseModel
from simcore_service_webserver.groups.schemas import (
    AllUsersGroups,
    GroupAccessRights,
    GroupUser,
    UsersGroup,
)


def test_models_library_and_postgress_database_enums_are_in_sync():
    # For the moment these two libraries they do not have a common library to share these
    # basic types so we test here that they are in sync

    def to_dict(enum_cls: type[enum.Enum]) -> dict[str, Any]:
        return {m.name: m.value for m in enum_cls}

    assert to_dict(simcore_postgres_database.models.groups.GroupType) == to_dict(
        models_library.groups.GroupType
    )


@pytest.mark.parametrize(
    "model_cls",
    (
        GroupAccessRights,
        AllUsersGroups,
        GroupUser,
        UsersGroup,
    ),
)
def test_group_models_examples(
    model_cls: type[BaseModel], model_cls_examples: dict[str, Any]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"

        #
        # UsersGroupEnveloped
        # AllUsersGroupsEnveloped
        # GroupUsersArrayEnveloped
        # GroupUserEnveloped
        #

        model_enveloped = Envelope[model_cls].parse_data(
            model_instance.dict(by_alias=True)
        )
        model_array_enveloped = Envelope[list[model_cls]].parse_data(
            [
                model_instance.dict(by_alias=True),
                model_instance.dict(by_alias=True),
            ]
        )

        assert model_enveloped.error is None
        assert model_array_enveloped.error is None


def test_sanitize_legacy_data():
    users_group_1 = UsersGroup.parse_obj(
        {
            "gid": "27",
            "label": "A user",
            "description": "A very special user",
            "thumbnail": "",  # <--- empty strings
            "accessRights": {"read": True, "write": False, "delete": False},
        }
    )

    assert users_group_1.thumbnail is None

    users_group_2 = UsersGroup.parse_obj(
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
