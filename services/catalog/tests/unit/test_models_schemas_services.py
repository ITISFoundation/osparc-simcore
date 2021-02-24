# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from pprint import pformat

import pytest
from simcore_service_catalog.models.schemas.services import (
    ServiceItem,
    ServiceOut,
    ServiceUpdate,
)


@pytest.mark.parametrize("model_cls", (ServiceOut, ServiceUpdate, ServiceItem))
def test_service_api_models_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"
