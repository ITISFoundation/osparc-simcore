# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pprint import pformat
from typing import Any, Dict, Type

import pytest
from models_library.service_settings_labels import (
    SimcoreServiceLabels,
    SimcoreServiceSettingLabelEntry,
    SimcoreServiceSettingsLabel,
)
from pydantic import BaseModel


def test_service_settings() -> None:
    simcore_settings_settings_label = SimcoreServiceSettingsLabel.parse_obj(
        SimcoreServiceSettingLabelEntry.Config.schema_extra["examples"]
    )
    assert simcore_settings_settings_label

    # ensure private attribute assignment
    for service_setting in simcore_settings_settings_label:
        # pylint: disable=protected-access
        service_setting._destination_container = "random_value"


SIMCORE_SERVICE_EXAMPLES = [
    (example, items, uses_dynamic_sidecar, index)
    # pylint: disable=unnecessary-comprehension
    for example, items, uses_dynamic_sidecar, index in zip(
        SimcoreServiceLabels.Config.schema_extra["examples"],
        [1, 2, 4],
        [False, True, True],
        ["legacy", "dynamic-service", "dynamic-service-with-compose-spec"],
    )
]


@pytest.mark.parametrize(
    "example, items, uses_dynamic_sidecar",
    [
        (example, items, uses_dynamic_sidecar)
        for example, items, uses_dynamic_sidecar, _ in SIMCORE_SERVICE_EXAMPLES
    ],
    ids=[i for _, _, _, i in SIMCORE_SERVICE_EXAMPLES],
)
def test_simcore_service_labels(
    example: Dict, items: int, uses_dynamic_sidecar: bool
) -> None:
    simcore_service_labels = SimcoreServiceLabels.parse_obj(example)
    assert simcore_service_labels
    assert len(simcore_service_labels.dict(exclude_unset=True)) == items
    assert simcore_service_labels.needs_dynamic_sidecar == uses_dynamic_sidecar


@pytest.mark.parametrize(
    "model_cls",
    (
        SimcoreServiceSettingLabelEntry,
        SimcoreServiceSettingsLabel,
        SimcoreServiceLabels,
    ),
)
def test_service_settings_model_examples(
    model_cls: Type[BaseModel], model_cls_examples: Dict[str, Dict[str, Any]]
) -> None:
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


def test_correctly_detect_dynamic_sidecar_boot(
    model_cls_examples: Dict[str, Dict[str, Any]]
) -> None:
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = SimcoreServiceLabels(**example)
        assert model_instance.needs_dynamic_sidecar == (
            "simcore.service.paths-mapping" in example
        )


def test_raises_error_if_http_entrypoint_is_missing() -> None:
    simcore_service_labels: Dict[str, Any] = SimcoreServiceLabels.Config.schema_extra[
        "examples"
    ][2]
    del simcore_service_labels["simcore.service.container-http-entrypoint"]

    with pytest.raises(ValueError):
        simcore_service = SimcoreServiceLabels(**simcore_service_labels)
