from pprint import pformat

import pytest
from simcore_service_webserver.users_models import (
    GroupAccessRights,
    GroupUser,
    ProfileOutput,
    Token,
    UsersGroup,
)


@pytest.mark.parametrize(
    "model_cls",
    (
        GroupAccessRights,
        GroupUser,
        ProfileOutput,
        Token,
        UsersGroup,
    ),
)
def test_user_models_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"
