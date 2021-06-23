# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pprint import pformat
from typing import Any, Dict

import pytest
from models_library.service_settings import (
    SimcoreServiceLabels,
    SimcoreServiceSettingLabelEntry,
    SimcoreServiceSettingsLabel,
)
from pydantic import BaseModel


def test_service_settings():
    service_settings_instance = SimcoreServiceSettingsLabel.parse_obj(
        SimcoreServiceSettingLabelEntry.Config.schema_extra["examples"]
    )
    assert service_settings_instance

    # ensure private attribute assignment
    for service_setting in service_settings_instance:
        # pylint: disable=protected-access
        service_setting._destination_container = "random_value"


SIMCORE_SERVICE_EXAMPLES = [
    (example, items, index)
    # pylint: disable=unnecessary-comprehension
    for example, items, index in zip(
        SimcoreServiceLabels.Config.schema_extra["examples"],
        [1, 2, 4],
        ["legacy", "dynamic-service", "dynamic-service-with-compose-spec"],
    )
]


@pytest.mark.parametrize(
    "example, items",
    [(example, items) for example, items, _ in SIMCORE_SERVICE_EXAMPLES],
    ids=[i for _, _, i in SIMCORE_SERVICE_EXAMPLES],
)
def test_simcore_service_labels(example: Dict, items: int):
    simcore_service = SimcoreServiceLabels.parse_obj(example)
    assert simcore_service
    assert len(simcore_service.dict(exclude_unset=True)) == items


@pytest.mark.parametrize(
    "model_cls",
    (
        SimcoreServiceSettingLabelEntry,
        SimcoreServiceSettingsLabel,
        SimcoreServiceLabels,
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
    (SimcoreServiceLabels,),
)
def test_correctly_detect_dynamic_sidecar_boot(
    model_cls: BaseModel, model_cls_examples: Dict[str, Dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance.needs_dynamic_sidecar == (
            "simcore.service.paths-mapping" in example
        )


def test_raises_error_if_http_entrypoint_is_missing():
    data: Dict[str, Any] = SimcoreServiceLabels.Config.schema_extra["examples"][2]
    del data["simcore.service.container-http-entrypoint"]

    with pytest.raises(ValueError):
        simcore_service = SimcoreServiceLabels(**data)
