# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections import namedtuple
from copy import deepcopy
from pprint import pformat
from typing import Any, Dict, Type

import pytest
from models_library.service_settings_labels import (
    PathMappingsLabel,
    SimcoreServiceLabels,
    SimcoreServiceSettingLabelEntry,
    SimcoreServiceSettingsLabel,
)
from pydantic import BaseModel, ValidationError

SimcoreServiceExample = namedtuple(
    "SimcoreServiceExample", "example, items, uses_dynamic_sidecar, id"
)


SIMCORE_SERVICE_EXAMPLES = [
    SimcoreServiceExample(
        example=SimcoreServiceLabels.Config.schema_extra["examples"][0],
        items=1,
        uses_dynamic_sidecar=False,
        id="legacy",
    ),
    SimcoreServiceExample(
        example=SimcoreServiceLabels.Config.schema_extra["examples"][1],
        items=3,
        uses_dynamic_sidecar=True,
        id="dynamic-service",
    ),
    SimcoreServiceExample(
        example=SimcoreServiceLabels.Config.schema_extra["examples"][2],
        items=5,
        uses_dynamic_sidecar=True,
        id="dynamic-service-with-compose-spec",
    ),
]


@pytest.mark.parametrize(
    "example, items, uses_dynamic_sidecar",
    [(x.example, x.items, x.uses_dynamic_sidecar) for x in SIMCORE_SERVICE_EXAMPLES],
    ids=[x.id for x in SIMCORE_SERVICE_EXAMPLES],
)
def test_simcore_service_labels(
    example: Dict, items: int, uses_dynamic_sidecar: bool
) -> None:
    simcore_service_labels = SimcoreServiceLabels.parse_obj(example)

    assert simcore_service_labels
    assert len(simcore_service_labels.dict(exclude_unset=True)) == items
    assert simcore_service_labels.needs_dynamic_sidecar == uses_dynamic_sidecar


def test_service_settings() -> None:
    simcore_settings_settings_label = SimcoreServiceSettingsLabel.parse_obj(
        SimcoreServiceSettingLabelEntry.Config.schema_extra["examples"]
    )
    assert simcore_settings_settings_label
    assert len(simcore_settings_settings_label) == len(
        SimcoreServiceSettingLabelEntry.Config.schema_extra["examples"]
    )
    assert simcore_settings_settings_label[0]

    # ensure private attribute assignment
    for service_setting in simcore_settings_settings_label:
        # pylint: disable=protected-access
        service_setting._destination_container = "random_value"


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


@pytest.mark.parametrize(
    "model_cls",
    (SimcoreServiceLabels,),
)
def test_correctly_detect_dynamic_sidecar_boot(
    model_cls: Type[BaseModel], model_cls_examples: Dict[str, Dict[str, Any]]
) -> None:
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance.needs_dynamic_sidecar == (
            "simcore.service.paths-mapping" in example
        )


def test_raises_error_if_http_entrypoint_is_missing() -> None:
    simcore_service_labels: Dict[str, Any] = deepcopy(
        SimcoreServiceLabels.Config.schema_extra["examples"][2]
    )
    del simcore_service_labels["simcore.service.container-http-entrypoint"]

    with pytest.raises(ValueError):
        SimcoreServiceLabels(**simcore_service_labels)


def test_path_mappings_none_state_paths() -> None:
    sample_data = deepcopy(PathMappingsLabel.Config.schema_extra["example"])
    sample_data["state_paths"] = None
    with pytest.raises(ValidationError):
        PathMappingsLabel(**sample_data)


def test_simcore_services_labels_compose_spec_null_container_http_entry_provided() -> None:
    sample_data = deepcopy(SimcoreServiceLabels.Config.schema_extra["examples"][2])
    assert sample_data["simcore.service.container-http-entrypoint"]

    sample_data["simcore.service.compose-spec"] = None
    with pytest.raises(ValidationError):
        SimcoreServiceLabels(**sample_data)


def test_raises_error_wrong_restart_policy() -> None:
    simcore_service_labels: Dict[str, Any] = deepcopy(
        SimcoreServiceLabels.Config.schema_extra["examples"][2]
    )
    simcore_service_labels["simcore.service.restart-policy"] = "__not_a_valid_policy__"

    with pytest.raises(ValueError):
        SimcoreServiceLabels(**simcore_service_labels)
