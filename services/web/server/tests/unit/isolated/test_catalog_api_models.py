# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module


from pprint import pformat

import pytest
from simcore_service_webserver.catalog_api_models import (
    ServiceInputApiOut,
    ServiceOutputApiOut,
)


@pytest.mark.parametrize(
    "model_cls",
    (
        ServiceInputApiOut,
        ServiceOutputApiOut,
    ),
)
def test_webserver_catalog_api_models(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"
