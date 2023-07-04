# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import json
from copy import deepcopy
from pprint import pformat
from typing import Any, NamedTuple

import pytest
from models_library.service_settings_labels import (
    DEFAULT_DNS_SERVER_ADDRESS,
    DEFAULT_DNS_SERVER_PORT,
    DNSResolver,
    DynamicSidecarServiceLabels,
    NATRule,
    PathMappingsLabel,
    SimcoreServiceLabels,
    SimcoreServiceSettingLabelEntry,
    SimcoreServiceSettingsLabel,
    _PortRange,
)
from models_library.services_resources import DEFAULT_SINGLE_SERVICE_NAME
from models_library.utils.string_substitution import TextTemplate
from pydantic import BaseModel, ValidationError


class _Parametrization(NamedTuple):
    example: dict[str, Any]
    items: int
    uses_dynamic_sidecar: bool


SIMCORE_SERVICE_EXAMPLES = {
    "legacy": _Parametrization(
        example=SimcoreServiceLabels.Config.schema_extra["examples"][0],
        items=1,
        uses_dynamic_sidecar=False,
    ),
    "dynamic-service": _Parametrization(
        example=SimcoreServiceLabels.Config.schema_extra["examples"][1],
        items=3,
        uses_dynamic_sidecar=True,
    ),
    "dynamic-service-with-compose-spec": _Parametrization(
        example=SimcoreServiceLabels.Config.schema_extra["examples"][2],
        items=5,
        uses_dynamic_sidecar=True,
    ),
}


@pytest.mark.parametrize(
    "example, items, uses_dynamic_sidecar",
    list(SIMCORE_SERVICE_EXAMPLES.values()),
    ids=list(SIMCORE_SERVICE_EXAMPLES.keys()),
)
def test_simcore_service_labels(example: dict, items: int, uses_dynamic_sidecar: bool):
    simcore_service_labels = SimcoreServiceLabels.parse_obj(example)

    assert simcore_service_labels
    assert len(simcore_service_labels.dict(exclude_unset=True)) == items
    assert simcore_service_labels.needs_dynamic_sidecar == uses_dynamic_sidecar


def test_service_settings():
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
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance.needs_dynamic_sidecar == (
            "simcore.service.paths-mapping" in example
        )


def test_raises_error_if_http_entrypoint_is_missing():
    simcore_service_labels: dict[str, Any] = deepcopy(
        SimcoreServiceLabels.Config.schema_extra["examples"][2]
    )
    del simcore_service_labels["simcore.service.container-http-entrypoint"]

    with pytest.raises(ValueError):
        SimcoreServiceLabels(**simcore_service_labels)


def test_path_mappings_none_state_paths():
    sample_data = deepcopy(PathMappingsLabel.Config.schema_extra["examples"][0])
    sample_data["state_paths"] = None
    with pytest.raises(ValidationError):
        PathMappingsLabel(**sample_data)


def test_path_mappings_json_encoding():
    for example in PathMappingsLabel.Config.schema_extra["examples"]:
        path_mappings = PathMappingsLabel.parse_obj(example)
        print(path_mappings)
        assert PathMappingsLabel.parse_raw(path_mappings.json()) == path_mappings


def test_simcore_services_labels_compose_spec_null_container_http_entry_provided():
    sample_data: dict[str, Any] = deepcopy(
        SimcoreServiceLabels.Config.schema_extra["examples"][2]
    )

    assert sample_data["simcore.service.container-http-entrypoint"]

    sample_data["simcore.service.compose-spec"] = None
    with pytest.raises(ValidationError):
        SimcoreServiceLabels(**sample_data)


def test_raises_error_wrong_restart_policy():
    simcore_service_labels: dict[str, Any] = deepcopy(
        SimcoreServiceLabels.Config.schema_extra["examples"][2]
    )
    simcore_service_labels["simcore.service.restart-policy"] = "__not_a_valid_policy__"

    with pytest.raises(ValueError):
        SimcoreServiceLabels(**simcore_service_labels)


def test_path_mappings_label_unsupported_size_constraints():
    with pytest.raises(ValidationError) as exec_into:
        PathMappingsLabel.parse_obj(
            {
                "outputs_path": "/ok_input_path",
                "inputs_path": "/ok_output_path",
                "state_paths": [],
                "volume_size_limits": {"/ok_input_path": "1d"},
            },
        )
    assert "Provided size='1d' contains invalid charactes:" in f"{exec_into.value}"


def test_path_mappings_label_defining_constraing_on_missing_path():
    with pytest.raises(ValidationError) as exec_into:
        PathMappingsLabel.parse_obj(
            {
                "outputs_path": "/ok_input_path",
                "inputs_path": "/ok_output_path",
                "state_paths": [],
                "volume_size_limits": {"/path_is_missing_from_above": "1"},
            },
        )
    assert (
        "path=PosixPath('/path_is_missing_from_above') not found in"
        in f"{exec_into.value}"
    )


def test_port_range():
    with pytest.raises(ValidationError):
        _PortRange(lower=1, upper=1)

    with pytest.raises(ValidationError):
        _PortRange(lower=20, upper=1)

    assert _PortRange(lower=1, upper=2)


def test_host_permit_list_policy():
    host_permit_list_policy = NATRule(
        hostname="hostname",
        tcp_ports=[
            _PortRange(lower=1, upper=3),
            99,
        ],
    )

    assert set(host_permit_list_policy.iter_tcp_ports()) == {1, 2, 3, 99}


@pytest.mark.parametrize(
    "container_permit_list, expected_host_permit_list_policy",
    [
        pytest.param(
            [
                {
                    "hostname": "a-host",
                    "tcp_ports": [12132, {"lower": 12, "upper": 2334}],
                }
            ],
            NATRule(
                hostname="a-host",
                tcp_ports=[12132, _PortRange(lower=12, upper=2334)],
                dns_resolver=DNSResolver(
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
                    "dns_resolver": {"address": "ns1.example.com", "port": 123},
                }
            ],
            NATRule(
                hostname="a-host",
                tcp_ports=[12132, _PortRange(lower=12, upper=2334)],
                dns_resolver=DNSResolver(address="ns1.example.com", port=123),
            ),
            id="with_dns_resolver",
        ),
    ],
)
def test_container_outgoing_permit_list_and_container_allow_internet_with_compose_spec(
    container_permit_list: dict[str, Any],
    expected_host_permit_list_policy: NATRule,
):
    container_name_1 = "test_container_1"
    container_name_2 = "test_container_2"
    compose_spec: dict[str, Any] = {
        "services": {container_name_1: None, container_name_2: None}
    }

    dict_data = {
        "simcore.service.containers-allowed-outgoing-permit-list": json.dumps(
            {container_name_1: container_permit_list}
        ),
        "simcore.service.containers-allowed-outgoing-internet": json.dumps(
            [container_name_2]
        ),
        "simcore.service.compose-spec": json.dumps(compose_spec),
        "simcore.service.container-http-entrypoint": container_name_1,
    }

    instance = DynamicSidecarServiceLabels.parse_raw(json.dumps(dict_data))
    assert (
        instance.containers_allowed_outgoing_permit_list[container_name_1][0]
        == expected_host_permit_list_policy
    )


def test_container_outgoing_permit_list_and_container_allow_internet_without_compose_spec():
    for dict_data in (
        # singles service with outgoing-permit-list
        {
            "simcore.service.containers-allowed-outgoing-permit-list": json.dumps(
                {
                    DEFAULT_SINGLE_SERVICE_NAME: [
                        {
                            "hostname": "a-host",
                            "tcp_ports": [12132, {"lower": 12, "upper": 2334}],
                        }
                    ]
                }
            )
        },
        # singles service with allowed-outgoing-internet
        {
            "simcore.service.containers-allowed-outgoing-internet": json.dumps(
                [DEFAULT_SINGLE_SERVICE_NAME]
            )
        },
    ):
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


def test_container_outgoing_permit_list_no_compose_spec_not_ok():
    dict_data = {
        "simcore.service.containers-allowed-outgoing-permit-list": json.dumps(
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


def test_container_outgoing_permit_list_compose_spec_not_ok():
    container_name = "test_container"
    compose_spec: dict[str, Any] = {"services": {container_name: None}}
    dict_data = {
        "simcore.service.containers-allowed-outgoing-permit-list": json.dumps(
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
        f"Trying to permit list container='container_name' which was not found in {compose_spec=}"
        in f"{exec_info.value}"
    )


def test_not_allowed_in_both_permit_list_and_outgoing_internet():
    container_name = "test_container"
    compose_spec: dict[str, Any] = {"services": {container_name: None}}

    dict_data = {
        "simcore.service.containers-allowed-outgoing-permit-list": json.dumps(
            {container_name: [{"hostname": "a-host", "tcp_ports": [4]}]}
        ),
        "simcore.service.containers-allowed-outgoing-internet": json.dumps(
            [container_name]
        ),
        "simcore.service.compose-spec": json.dumps(compose_spec),
        "simcore.service.container-http-entrypoint": container_name,
    }

    with pytest.raises(ValidationError) as exec_info:
        DynamicSidecarServiceLabels.parse_raw(json.dumps(dict_data))

    assert (
        f"Not allowed common_containers={{'{container_name}'}} detected"
        in f"{exec_info.value}"
    )


@pytest.fixture
def vendor_environments() -> dict[str, Any]:
    return {
        "OSPARC_VARIABLE_VENDOR_SECRET_DNS_RESOLVER_ADDRESS": "172.0.0.1",
        "OSPARC_VARIABLE_VENDOR_SECRET_DNS_RESOLVER_PORT": 1234,
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENCE_HOSTNAME": "hostname",
        "OSPARC_VARIABLE_VENDOR_SECRET_TCP_PORTS": [
            1,
            2,
            3,
            4,
        ],
        "OSPARC_VARIABLE_VENDOR_SECRET_TCP_PORTS_1": 1,
        "OSPARC_VARIABLE_VENDOR_SECRET_TCP_PORTS_2": 2,
        "OSPARC_VARIABLE_VENDOR_SECRET_TCP_PORTS_3": 3,
    }


@pytest.fixture
def service_labels() -> dict[str, str]:
    return {
        "simcore.service.paths-mapping": json.dumps(
            {
                "inputs_path": "/tmp/inputs",
                "outputs_path": "/tmp/outputs",
                "state_paths": ["/tmp/save_1", "/tmp_save_2"],
                "state_exclude": ["/tmp/strip_me/*", "*.py"],
            }
        ),
        "simcore.service.compose-spec": json.dumps(
            {
                "version": "2.3",
                "services": {
                    "rt-web": {
                        "image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/sim4life:${SERVICE_VERSION}",
                        "init": True,
                        "depends_on": ["s4l-core"],
                    },
                    "s4l-core": {
                        "image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/s4l-core:${SERVICE_VERSION}",
                        "runtime": "nvidia",
                        "init": True,
                        "environment": ["DISPLAY=${DISPLAY}"],
                        "volumes": ["/tmp/.X11-unix:/tmp/.X11-unix"],
                    },
                },
            }
        ),
        "simcore.service.container-http-entrypoint": "rt-web",
        "simcore.service.restart-policy": "on-inputs-downloaded",
        "simcore.service.containers-allowed-outgoing-permit-list": json.dumps(
            {
                "s4l-core": [
                    {
                        "hostname": "license.com",
                        "tcp_ports": [
                            "$OSPARC_VARIABLE_VENDOR_SECRET_TCP_PORTS_1",
                            "$OSPARC_VARIABLE_VENDOR_SECRET_TCP_PORTS_2",
                            3,
                        ],
                        "dns_resolver": {
                            "address": "$OSPARC_VARIABLE_VENDOR_SECRET_DNS_RESOLVER_ADDRESS",
                            "port": "$OSPARC_VARIABLE_VENDOR_SECRET_DNS_RESOLVER_PORT",
                        },
                    }
                ]
            }
        ),
        "simcore.service.settings": json.dumps(
            [
                {
                    "name": "constraints",
                    "type": "string",
                    "value": ["node.platform.os == linux"],
                },
                {
                    "name": "ContainerSpec",
                    "type": "ContainerSpec",
                    "value": {"Command": ["run"]},
                },
                {
                    "name": "Resources",
                    "type": "Resources",
                    "value": {
                        "Limits": {"NanoCPUs": 4000000000, "MemoryBytes": 17179869184},
                        "Reservations": {
                            "NanoCPUs": 100000000,
                            "MemoryBytes": 536870912,
                            "GenericResources": [
                                {"DiscreteResourceSpec": {"Kind": "VRAM", "Value": 1}}
                            ],
                        },
                    },
                },
                {
                    "name": "mount",
                    "type": "object",
                    "value": [
                        {
                            "ReadOnly": True,
                            "Source": "/tmp/.X11-unix",
                            "Target": "/tmp/.X11-unix",
                            "Type": "bind",
                        }
                    ],
                },
                {
                    "name": "env",
                    "type": "string",
                    "value": ["DISPLAY=${DISPLAY}"],
                },
                {
                    "name": "ports",
                    "type": "int",
                    "value": 8888,
                },
                {
                    "name": "resources",
                    "type": "Resources",
                    "value": {
                        "Limits": {"NanoCPUs": 4000000000, "MemoryBytes": 8589934592}
                    },
                },
            ]
        ),
    }


@pytest.mark.xfail(reason="Needs enabling OEnvSubstitutionStr (coming PR)")
def test_can_parse_labels_with_osparc_identifiers(
    vendor_environments: dict[str, Any], service_labels: dict[str, str]
):
    # can load OSPARC_VARIABLE_ identifiers!!
    service_meta = SimcoreServiceLabels.parse_obj(service_labels)

    assert service_meta.containers_allowed_outgoing_permit_list["s4l-core"][
        0
    ].tcp_ports == [
        "$OSPARC_VARIABLE_VENDOR_SECRET_TCP_PORTS_1",
        "$OSPARC_VARIABLE_VENDOR_SECRET_TCP_PORTS_2",
        3,
    ]

    service_meta_str = TextTemplate(
        service_meta.json(include={"containers_allowed_outgoing_permit_list"})
    ).safe_substitute(vendor_environments)

    assert "$" not in service_meta_str


@pytest.mark.xfail(reason="Needs enabling OEnvSubstitutionStr (coming PR)")
def test_resolving_some_service_labels_at_load_time(
    vendor_environments: dict[str, Any], service_labels: dict[str, str]
):

    print(json.dumps(service_labels, indent=1))

    # Resolving at load-time (some of them are possible)

    for label_name in (
        "simcore.service.compose-spec",
        "simcore.service.settings",
        "simcore.service.containers-allowed-outgoing-permit-list",
    ):
        template = TextTemplate(service_labels[label_name])
        if template.is_valid() and (identifiers := template.get_identifiers()):
            assert set(identifiers).issubset(vendor_environments)
            resolved_label: str = template.substitute(vendor_environments)
            service_labels[label_name] = json.dumps(json.loads(resolved_label))

    print(json.dumps(service_labels, indent=1))

    # NOTE: that this model needs all values to be resolved before parsing them
    # otherwise it might fail!! The question is whether these values can be resolved at this point
    # NOTE: vendor values are in the database and therefore are available at this point
    labels = SimcoreServiceLabels.parse_obj(service_labels)

    print("After", labels.json(indent=1))
