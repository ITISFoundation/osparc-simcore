from pprint import pformat
from typing import Any

import pytest
from models_library.generics import Envelope
from pydantic import BaseModel
from simcore_service_webserver.groups_models import (
    AllUsersGroups,
    GroupAccessRights,
    GroupUser,
    UsersGroup,
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
