# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pprint import pformat

import pytest
from simcore_postgres_database.models.users import UserRole
from simcore_service_api_server.models.schemas.profiles import Profile, UserRoleEnum


@pytest.mark.parametrize("model_cls", (Profile,))
def test_profiles_model_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


def test_enums_in_sync():
    # if this test fails, API needs to be updated
    assert set(e.value for e in UserRole) == set(e.value for e in UserRoleEnum)
