# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pprint import pformat
from typing import Any, Dict
from xml.etree.ElementInclude import include

import pytest
from models_library.service_settings import (
    SimcoreService,
    SimcoreServiceSetting,
    SimcoreServiceSettings,
)
from pydantic import BaseModel


@pytest.mark.parametrize(
    "model_cls",
    (
        SimcoreServiceSetting,
        SimcoreServiceSettings,
        SimcoreService,
    ),
)
def test_service_settings_model_examples(
    model_cls: BaseModel, model_cls_examples: Dict[str, Dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


@pytest.mark.parametrize(
    "model_cls",
    (SimcoreService,),
)
def test_correctly_detect_dynamic_sidecar_boot(
    model_cls: BaseModel, model_cls_examples: Dict[str, Dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance.needs_dynamic_sidecar == (
            True if "simcore.service.paths-mapping" in example else False
        )
