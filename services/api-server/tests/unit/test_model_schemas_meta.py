# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from pprint import pprint

import pytest
from simcore_service_api_server.models.schemas.meta import Meta


@pytest.mark.parametrize("model_cls", (Meta,))
def test_meta_model_examples(model_cls, model_cls_examples):
    for example in model_cls_examples:
        pprint(example)
        model_instance = model_cls(**example)
        assert model_instance
