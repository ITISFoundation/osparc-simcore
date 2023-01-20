# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from collections import namedtuple
from copy import deepcopy
from pprint import pformat
from typing import Any

import pytest
from models_library.service_settings_labels import (
    DEFAULT_DNS_SERVER_ADDRESS,
    DEFAULT_DNS_SERVER_PORT,
    DNResolver,
    DynamicSidecarServiceLabels,
    HostWhitelistPolicy,
    PathMappingsLabel,
    PortRange,
    SimcoreServiceLabels,
    SimcoreServiceSettingLabelEntry,
    SimcoreServiceSettingsLabel,
)
from models_library.services_resources import DEFAULT_SINGLE_SERVICE_NAME
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
    example: dict, items: int, uses_dynamic_sidecar: bool
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
        service_setting._destination_containers = ["random_value1", "random_value2"]


@pytest.mark.parametrize(
    "model_cls",
    (
        SimcoreServiceSettingLabelEntry,
        SimcoreServiceSettingsLabel,
        SimcoreServiceLabels,
    ),
)
def test_service_settings_model_examples(
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
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
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
) -> None:
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance.needs_dynamic_sidecar == (
            "simcore.service.paths-mapping" in example
        )


def test_raises_error_if_http_entrypoint_is_missing() -> None:
    simcore_service_labels: dict[str, Any] = deepcopy(
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


def test_path_mappings_json_encoding() -> None:
    example = PathMappingsLabel.Config.schema_extra["example"]
    path_mappings = PathMappingsLabel.parse_obj(example)
    print(path_mappings)
    assert PathMappingsLabel.parse_raw(path_mappings.json()) == path_mappings


def test_simcore_services_labels_compose_spec_null_container_http_entry_provided() -> None:
    sample_data = deepcopy(SimcoreServiceLabels.Config.schema_extra["examples"][2])
    assert sample_data["simcore.service.container-http-entrypoint"]

    sample_data["simcore.service.compose-spec"] = None
    with pytest.raises(ValidationError):
        SimcoreServiceLabels(**sample_data)


def test_raises_error_wrong_restart_policy() -> None:
    simcore_service_labels: dict[str, Any] = deepcopy(
        SimcoreServiceLabels.Config.schema_extra["examples"][2]
    )
    simcore_service_labels["simcore.service.restart-policy"] = "__not_a_valid_policy__"

    with pytest.raises(ValueError):
        SimcoreServiceLabels(**simcore_service_labels)


def test_port_range():
    with pytest.raises(ValidationError):
        PortRange(lower=1, upper=1)

    with pytest.raises(ValidationError):
        PortRange(lower=20, upper=1)

    assert PortRange(lower=1, upper=2)


def test_host_whitelist_policy():
    host_whitelist_policy = HostWhitelistPolicy(
        hostname="hostname",
        tcp_ports=[
            PortRange(lower=1, upper=12),
            22,
        ],
    )

    assert set(host_whitelist_policy.iter_tcp_ports()) == set(range(1, 12 + 1)) | {22}


@pytest.mark.parametrize(
    "container_whitelist, expected_host_whitelist_policy",
    [
        pytest.param(
            [
                {
                    "hostname": "a-host",
                    "tcp_ports": [12132, {"lower": 12, "upper": 2334}],
                }
            ],
            HostWhitelistPolicy(
                hostname="a-host",
                tcp_ports=[12132, PortRange(lower=12, upper=2334)],
                dns_resolver=DNResolver(
                    address=DEFAULT_DNS_SERVER_ADDRESS, port=DEFAULT_DNS_SERVER_PORT
                ),
            ),
            id="default_dns_resolver",
        ),
        pytest.param(
            [
                {
                    "hostname": "a-host",
                    "tcp_ports": [12132, {"lower": 12, "upper": 2334}],
                    "dns_resolver": {"address": "3.4.6.7", "port": 123},
                }
            ],
            HostWhitelistPolicy(
                hostname="a-host",
                tcp_ports=[12132, PortRange(lower=12, upper=2334)],
                dns_resolver=DNResolver(address="3.4.6.7", port=123),
            ),
            id="with_dns_resolver",
        ),
    ],
)
def test_container_outgoing_whitelist_and_container_allow_internet_with_compose_spec(
    container_whitelist: dict[str, Any],
    expected_host_whitelist_policy: HostWhitelistPolicy,
):
    container_name = "test_container"
    compose_spec: dict[str, Any] = {"services": {container_name: None}}

    dict_data = {
        "simcore.service.containers-allowed-outgoing-whitelist": json.dumps(
            {container_name: container_whitelist}
        ),
        "simcore.service.containers-allowed-outgoing-internet": json.dumps(
            [container_name]
        ),
        "simcore.service.compose-spec": json.dumps(compose_spec),
        "simcore.service.container-http-entrypoint": container_name,
    }

    instance = DynamicSidecarServiceLabels.parse_raw(json.dumps(dict_data))
    assert (
        instance.containers_allowed_outgoing_whitelist[container_name][0]
        == expected_host_whitelist_policy
    )


def test_container_outgoing_whitelist_and_container_allow_internet_without_compose_spec():
    dict_data = {
        "simcore.service.containers-allowed-outgoing-whitelist": json.dumps(
            {
                DEFAULT_SINGLE_SERVICE_NAME: [
                    {
                        "hostname": "a-host",
                        "tcp_ports": [12132, {"lower": 12, "upper": 2334}],
                    }
                ]
            }
        ),
        "simcore.service.containers-allowed-outgoing-internet": json.dumps(
            [DEFAULT_SINGLE_SERVICE_NAME]
        ),
    }
    assert DynamicSidecarServiceLabels.parse_raw(json.dumps(dict_data))


def test_container_allow_internet_no_compose_spec_not_ok():
    dict_data = {
        "simcore.service.containers-allowed-outgoing-internet": json.dumps(["hoho"]),
    }
    with pytest.raises(ValidationError) as exec_info:
        assert DynamicSidecarServiceLabels.parse_raw(json.dumps(dict_data))

    assert "Expected only 1 entry 'container' not '{'hoho'}" in f"{exec_info.value}"


def test_container_allow_internet_compose_spec_not_ok():
    container_name = "test_container"
    compose_spec: dict[str, Any] = {"services": {container_name: None}}
    dict_data = {
        "simcore.service.compose-spec": json.dumps(compose_spec),
        "simcore.service.containers-allowed-outgoing-internet": json.dumps(["hoho"]),
    }
    with pytest.raises(ValidationError) as exec_info:
        assert DynamicSidecarServiceLabels.parse_raw(json.dumps(dict_data))

    assert f"container='hoho' not found in {compose_spec=}" in f"{exec_info.value}"


def test_container_outgoing_whitelist_no_compose_spec_not_ok():
    dict_data = {
        "simcore.service.containers-allowed-outgoing-whitelist": json.dumps(
            {
                "container_name": [
                    {
                        "hostname": "a-host",
                        "tcp_ports": [12132, {"lower": 12, "upper": 2334}],
                    }
                ]
            }
        ),
    }
    with pytest.raises(ValidationError) as exec_info:
        assert DynamicSidecarServiceLabels.parse_raw(json.dumps(dict_data))
    assert (
        f"Expected only one entry '{DEFAULT_SINGLE_SERVICE_NAME}' not 'container_name'"
        in f"{exec_info.value}"
    )


def test_container_outgoing_whitelist_compose_spec_not_ok():
    container_name = "test_container"
    compose_spec: dict[str, Any] = {"services": {container_name: None}}
    dict_data = {
        "simcore.service.containers-allowed-outgoing-whitelist": json.dumps(
            {
                "container_name": [
                    {
                        "hostname": "a-host",
                        "tcp_ports": [12132, {"lower": 12, "upper": 2334}],
                    }
                ]
            }
        ),
        "simcore.service.compose-spec": json.dumps(compose_spec),
    }
    with pytest.raises(ValidationError) as exec_info:
        assert DynamicSidecarServiceLabels.parse_raw(json.dumps(dict_data))
    assert (
        f"Trying to whitelist container='container_name' which was not found in {compose_spec=}"
        in f"{exec_info.value}"
    )
