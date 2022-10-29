# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from pprint import pformat

import pytest
from simcore_service_catalog.models.schemas.services import (
    ServiceGet,
    ServiceItem,
    ServiceUpdate,
)
from simcore_service_catalog.models.schemas.services_ports import ServicePortGet


@pytest.mark.parametrize(
    "model_cls",
    (
        ServiceGet,
        ServiceUpdate,
        ServiceItem,
        ServicePortGet,
    ),
)
def test_service_api_models_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"
