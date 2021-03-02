# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from pprint import pformat

import pytest
from simcore_service_api_server.models.schemas.profiles import Profile


@pytest.mark.parametrize("model_cls", (Profile,))
def test_profiles_model_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"
