# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any

import pytest
from common_library.dict_tools import (
    copy_from_dict,
    get_from_dict,
    remap_keys,
    update_dict,
)


@pytest.fixture
def data() -> dict[str, Any]:
    return {
        "ID": "3ifd79yhz2vpgu1iz43mf9m2d",
        "Version": {"Index": 176},
        "CreatedAt": "2021-11-10T17:09:01.892109221Z",
        "UpdatedAt": "2021-11-10T17:09:35.291164864Z",
        "Labels": {},
        "Spec": {
            "ContainerSpec": {
                "Image": "local/api-server:production",
                "Labels": {"com.docker.stack.namespace": "master-simcore"},
                "Hostname": "{{.Node.Hostname}}-{{.Service.Name}}-{{.Task.Slot}}",
                "Env": [
                    "API_SERVER_DEV_FEATURES_ENABLED=1",
                    "BF_API_KEY=none",
                    "BF_API_SECRET=none",
                ],
                "Privileges": {"CredentialSpec": None, "SELinuxContext": None},
                "Init": True,
                "Isolation": "default",
            },
            "Resources": {},
            "Placement": {},
            "Networks": [
                {"Target": "roybucjnp44t561jvgy47dd14", "Aliases": ["api-server"]}
            ],
            "ForceUpdate": 0,
        },
        "ServiceID": "77hyhjm6bqs81xp5g3e4ov7wv",
        "Slot": 1,
        "NodeID": "iz7unuzyzuxbpr80kzheskbbf",
        "Status": {
            "Timestamp": "2021-11-10T17:09:35.237847117Z",
            "State": "running",
            "Message": "started",
            "ContainerStatus": {
                "ContainerID": "8dadeb42eecbcb58295e0508c27c76d46f5106859af30276abcdcd4e4608f39c",
                "PID": 1772378,
                "ExitCode": 0,
            },
            "PortStatus": {},
        },
        "DesiredState": "running",
        "NetworksAttachments": [
            {
                "Network": {
                    "ID": "q6ojghy5phzllv63cmwhorbhy",
                    "Version": {"Index": 6},
                    "CreatedAt": "2021-11-10T17:08:36.840863313Z",
                    "UpdatedAt": "2021-11-10T17:08:36.846648842Z",
                    "Spec": {
                        "Name": "ingress",
                        "Labels": {},
                        "DriverConfiguration": {},
                        "Ingress": True,
                        "IPAMOptions": {"Driver": {}},
                        "Scope": "swarm",
                    },
                    "DriverState": {
                        "Name": "overlay",
                        "Options": {
                            "com.docker.network.driver.overlay.vxlanid_list": "4096"
                        },
                    },
                    "IPAMOptions": {
                        "Driver": {"Name": "default"},
                        "Configs": [{"Subnet": "10.1.1.0/24", "Gateway": "10.1.1.1"}],
                    },
                },
                "Addresses": ["10.1.1.24/24"],
            },
            {
                "Network": {
                    "ID": "roybucjnp44t561jvgy47dd14",
                    "Version": {"Index": 14},
                    "CreatedAt": "2021-11-10T17:08:37.532148857Z",
                    "UpdatedAt": "2021-11-10T17:08:37.533461228Z",
                    "Spec": {
                        "Name": "master-simcore_default",
                        "Labels": {"com.docker.stack.namespace": "master-simcore"},
                        "DriverConfiguration": {"Name": "overlay"},
                        "Attachable": True,
                        "Scope": "swarm",
                    },
                    "DriverState": {
                        "Name": "overlay",
                        "Options": {
                            "com.docker.network.driver.overlay.vxlanid_list": "4098"
                        },
                    },
                    "IPAMOptions": {
                        "Driver": {"Name": "default"},
                        "Configs": [{"Subnet": "10.0.1.0/24", "Gateway": "10.0.1.1"}],
                    },
                },
                "Addresses": ["10.1.1.1/24"],
            },
        ],
    }


def test_remap_keys():
    assert remap_keys({"a": 1, "b": 2}, rename={"a": "A"}) == {"A": 1, "b": 2}


def test_update_dict():
    def _increment(x):
        return x + 1

    data = {"a": 1, "b": 2, "c": 3}

    assert update_dict(data, a=_increment, b=42) == {"a": 2, "b": 42, "c": 3}


def test_get_from_dict(data: dict[str, Any]):

    assert get_from_dict(data, "Spec.ContainerSpec.Labels") == {
        "com.docker.stack.namespace": "master-simcore"
    }
    # TODO: see that dotted keys cannot be used here,
    assert get_from_dict(data, "Invalid.Invalid.Invalid", default=42) == 42


def test_copy_from_dict(data: dict[str, Any]):

    selected_data = copy_from_dict(
        data,
        include={
            "ID": ...,
            "CreatedAt": ...,
            "UpdatedAt": ...,
            "Spec": {"ContainerSpec": {"Image"}},
            "Status": {"Timestamp", "State", "ContainerStatus"},
            "DesiredState": ...,
        },
    )

    assert selected_data["ID"] == data["ID"]
    assert (
        selected_data["Spec"]["ContainerSpec"]["Image"]
        == data["Spec"]["ContainerSpec"]["Image"]
    )
    assert selected_data["Status"]["State"] == data["Status"]["State"]
    assert "Message" not in selected_data["Status"]["State"]
    assert "running" in data["Status"]["State"]
