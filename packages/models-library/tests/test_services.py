# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import re
from copy import deepcopy
from pprint import pformat
from typing import Any, Callable, Dict, List

import pytest
from models_library.basic_regex import VERSION_RE
from models_library.services import (
    COMPUTATIONAL_SERVICE_KEY_FORMAT,
    DYNAMIC_SERVICE_KEY_FORMAT,
    SERVICE_KEY_RE,
    BootOption,
    ServiceDockerData,
    ServiceInput,
    ServiceMetaData,
    ServiceOutput,
    _BaseServiceCommonDataModel,
)
from models_library.services_db import ServiceAccessRightsAtDB, ServiceMetaDataAtDB


@pytest.fixture()
def minimal_service_common_data() -> Dict[str, Any]:
    return dict(
        name="this is a nice sample service",
        description="this is the description of the service",
    )


def test_create_minimal_service_common_data(
    minimal_service_common_data: Dict[str, Any]
):
    service = _BaseServiceCommonDataModel(**minimal_service_common_data)

    assert service.name == minimal_service_common_data["name"]
    assert service.description == minimal_service_common_data["description"]
    assert service.thumbnail == None


def test_node_with_empty_thumbnail(minimal_service_common_data: Dict[str, Any]):
    service_data = minimal_service_common_data
    service_data.update({"thumbnail": ""})

    service = _BaseServiceCommonDataModel(**minimal_service_common_data)

    assert service.name == minimal_service_common_data["name"]
    assert service.description == minimal_service_common_data["description"]
    assert service.thumbnail == None


def test_node_with_thumbnail(minimal_service_common_data: Dict[str, Any]):
    service_data = minimal_service_common_data
    service_data.update(
        {
            "thumbnail": "https://www.google.com/imgres?imgurl=http%3A%2F%2Fclipart-library.com%2Fimages%2FpT5ra4Xgc.jpg&imgrefurl=http%3A%2F%2Fclipart-library.com%2Fcool-pictures.html&tbnid=6Cgc0X9Jo24p3M&vet=12ahUKEwiW3Kbd8KruAhUHzaQKHbvtApwQMygAegUIARCaAQ..i&docid=QuGKBFIIEGuLhM&w=1920&h=1080&q=some%20cool%20images&ved=2ahUKEwiW3Kbd8KruAhUHzaQKHbvtApwQMygAegUIARCaAQ"
        }
    )

    service = _BaseServiceCommonDataModel(**minimal_service_common_data)

    assert service.name == minimal_service_common_data["name"]
    assert service.description == minimal_service_common_data["description"]
    assert (
        service.thumbnail
        == "https://www.google.com/imgres?imgurl=http%3A%2F%2Fclipart-library.com%2Fimages%2FpT5ra4Xgc.jpg&imgrefurl=http%3A%2F%2Fclipart-library.com%2Fcool-pictures.html&tbnid=6Cgc0X9Jo24p3M&vet=12ahUKEwiW3Kbd8KruAhUHzaQKHbvtApwQMygAegUIARCaAQ..i&docid=QuGKBFIIEGuLhM&w=1920&h=1080&q=some%20cool%20images&ved=2ahUKEwiW3Kbd8KruAhUHzaQKHbvtApwQMygAegUIARCaAQ"
    )


@pytest.mark.parametrize(
    "model_cls",
    (
        ServiceInput,
        ServiceOutput,
        BootOption,
    ),
)
def test_service_models_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


@pytest.mark.parametrize(
    "service_key",
    [
        "simcore/services/frontend/file-picker",
        "simcore/services/frontend/nodes-group",
        "simcore/services/comp/cardiac_myocyte_grandi",
        "simcore/services/comp/human-gb-0d-cardiac-model",
        "simcore/services/comp/human-gb-1d-cardiac-model",
        "simcore/services/comp/human-gb-2d-cardiac-model",
        "simcore/services/comp/human-ord-0d-cardiac-model",
        "simcore/services/comp/human-ord-1d-cardiac-model",
        "simcore/services/comp/human-ord-2d-cardiac-model",
        "simcore/services/comp/itis/sleeper",
        "simcore/services/comp/itis/sleeper-gpu",
        "simcore/services/comp/itis/sleeper-mpi",
        "simcore/services/comp/kember-cardiac-model",
        "simcore/services/comp/mithra",
        "simcore/services/comp/opencor",
        "simcore/services/comp/osparc-opencor",
        "simcore/services/comp/osparc-python-runner",
        "simcore/services/comp/pmr_mrg",
        "simcore/services/comp/rabbit-ss-0d-cardiac-model",
        "simcore/services/comp/rabbit-ss-1d-cardiac-model",
        "simcore/services/comp/rabbit-ss-2d-cardiac-model",
        "simcore/services/comp/spike_multilevel1",
        "simcore/services/comp/spike_multilevel2",
        "simcore/services/comp/ucdavis-singlecell-cardiac-model",
        "simcore/services/comp/usf-simrun",
        "simcore/services/dynamic/3d-viewer",
        "simcore/services/dynamic/3d-viewer-gpu",
        "simcore/services/dynamic/3d-viewer",
        "simcore/services/dynamic/3d-viewer-gpu",
        "simcore/services/dynamic/bornstein-viewer",
        "simcore/services/dynamic/btl-pc",
        "simcore/services/dynamic/cc-0d-viewer",
        "simcore/services/dynamic/cc-1d-viewer",
        "simcore/services/dynamic/cc-2d-viewer",
        "simcore/services/dynamic/jupyter-base-notebook",
        "simcore/services/dynamic/jupyter-fenics",
        "simcore/services/dynamic/jupyter-octave-python-math",
        "simcore/services/dynamic/jupyter-r-notebook",
        "simcore/services/dynamic/jupyter-scipy-notebook",
        "simcore/services/dynamic/kember-viewer",
        "simcore/services/dynamic/mapcore-widget",
        "simcore/services/dynamic/mattward-viewer",
        "simcore/services/dynamic/raw-graphs",
        "simcore/services/dynamic/raw-graphs-table",
        "simcore/services/dynamic/tissue-properties",
    ],
)
@pytest.mark.parametrize(
    "regex_pattern",
    [SERVICE_KEY_RE, r"^(simcore)/(services)/(comp|dynamic|frontend)(/[^\s/]+)+$"],
    ids=["pattern_with_w", "pattern_with_s"],
)
def test_service_key_regex_patterns(service_key: str, regex_pattern: str):
    match = re.match(regex_pattern, service_key)
    assert match

    assert match.group(1) == "simcore"
    assert match.group(2) == "services"
    assert match.group(3) in ["comp", "dynamic", "frontend"]
    assert match.group(4) is not None

    # tests formatters
    new_service_key = None
    service_type = match.group(3)
    service_name = match.group(4).strip(
        "/"
    )  # FIXME: SERVICE_KEY_RE MUST eliminate / in the last capture!!!
    if service_type == "comp":
        new_service_key = COMPUTATIONAL_SERVICE_KEY_FORMAT.format(
            service_name=service_name
        )
    elif service_type == "dynamic":
        new_service_key = DYNAMIC_SERVICE_KEY_FORMAT.format(service_name=service_name)

    if new_service_key:
        new_match = re.match(regex_pattern, new_service_key)
        assert new_match
        assert new_match.groups() == match.groups()


@pytest.mark.parametrize(
    "model_cls",
    (ServiceAccessRightsAtDB, ServiceMetaDataAtDB, ServiceMetaData, ServiceDockerData),
)
def test_services_model_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


@pytest.mark.parametrize(
    "python_regex_pattern, json_schema_file_name, json_schema_entry_paths",
    [
        (SERVICE_KEY_RE, "project-v0.0.1.json", ["key"]),
        (VERSION_RE, "project-v0.0.1.json", ["version"]),
        (VERSION_RE, "node-meta-v0.0.1.json", ["version"]),
        (SERVICE_KEY_RE, "node-meta-v0.0.1.json", ["key"]),
    ],
)
def test_same_regex_patterns_in_jsonschema_and_python(
    python_regex_pattern: str,
    json_schema_file_name: str,
    json_schema_entry_paths: List[str],
    json_schema_dict: Callable,
):
    # read file in
    json_schema_config = json_schema_dict(json_schema_file_name)
    # go to keys
    def _find_pattern_entry(obj: Dict[str, Any], key: str) -> Any:
        if key in obj:
            return obj[key]["pattern"]
        for v in obj.values():
            if isinstance(v, dict):
                item = _find_pattern_entry(v, key)
                if item is not None:
                    return item
        return None

    for x_path in json_schema_entry_paths:
        json_pattern = _find_pattern_entry(json_schema_config, x_path)
        assert json_pattern == python_regex_pattern


def test_boot_option_wrong_default() -> None:
    for example in [deepcopy(x) for x in BootOption.Config.schema_extra["examples"]]:
        with pytest.raises(ValueError):
            example["default"] = "__undefined__"
            assert BootOption(**example)
