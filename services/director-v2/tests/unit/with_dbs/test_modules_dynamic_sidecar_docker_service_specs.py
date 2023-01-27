# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument


import json
from typing import Any, cast

import pytest
import respx
from fastapi import FastAPI
from models_library.aiodocker_api import AioDockerServiceSpec
from models_library.service_settings_labels import (
    SimcoreServiceLabels,
    SimcoreServiceSettingsLabel,
)
from models_library.services import RunID, ServiceKeyVersion
from pytest import MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from servicelib.json_serialization import json_dumps
from simcore_service_director_v2.core.settings import DynamicSidecarSettings
from simcore_service_director_v2.models.schemas.dynamic_services import SchedulerData
from simcore_service_director_v2.modules.catalog import CatalogClient
from simcore_service_director_v2.modules.dynamic_sidecar.docker_service_specs import (
    get_dynamic_sidecar_spec,
)
from simcore_service_director_v2.utils.dict_utils import nested_update


@pytest.fixture
def mock_env(monkeypatch: MonkeyPatch, mock_env: EnvVarsDict) -> EnvVarsDict:
    """overrides unit/conftest:mock_env fixture"""
    env_vars = mock_env.copy()
    env_vars.update(
        {
            "DYNAMIC_SIDECAR_IMAGE": "local/dynamic-sidecar:MOCK",
            "LOG_LEVEL": "DEBUG",
            "POSTGRES_DB": "test",
            "POSTGRES_ENDPOINT": "localhost:5432",
            "POSTGRES_HOST": "localhost",
            "POSTGRES_PASSWORD": "test",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": "test",
            "R_CLONE_ENABLED": "False",
            "R_CLONE_PROVIDER": "MINIO",
            "RABBIT_HOST": "rabbit",
            "RABBIT_PASSWORD": "adminadmin",
            "RABBIT_PORT": "5672",
            "RABBIT_USER": "admin",
            "REGISTRY_AUTH": "false",
            "REGISTRY_PW": "test",
            "REGISTRY_SSL": "false",
            "REGISTRY_URL": "foo.bar.com",
            "REGISTRY_USER": "test",
            "S3_ACCESS_KEY": "12345678",
            "S3_BUCKET_NAME": "simcore",
            "S3_ENDPOINT": "http://172.17.0.1:9001",
            "S3_SECRET_KEY": "12345678",
            "S3_SECURE": "False",
            "SC_BOOT_MODE": "production",
            "SIMCORE_SERVICES_NETWORK_NAME": "simcore_services_network_name",
            "SWARM_STACK_NAME": "test_swarm_name",
            "TRAEFIK_SIMCORE_ZONE": "test_traefik_zone",
        }
    )
    setenvs_from_dict(monkeypatch, env_vars)
    return env_vars


@pytest.fixture
def dynamic_sidecar_settings(mock_env: dict[str, str]) -> DynamicSidecarSettings:
    return DynamicSidecarSettings.create_from_envs()


@pytest.fixture
def swarm_network_id() -> str:
    return "mocked_swarm_network_id"


@pytest.fixture
def simcore_service_labels() -> SimcoreServiceLabels:
    # overwrites global fixture
    return SimcoreServiceLabels.parse_obj(
        SimcoreServiceLabels.Config.schema_extra["examples"][2]
    )


@pytest.fixture
def expected_dynamic_sidecar_spec(run_id: RunID) -> dict[str, Any]:
    return {
        "endpoint_spec": {},
        "labels": {
            "io.simcore.scheduler-data": SchedulerData.parse_obj(
                {
                    "compose_spec": '{"version": "2.3", "services": {"rt-web": {"image": '
                    '"${SIMCORE_REGISTRY}/simcore/services/dynamic/sim4life:${SERVICE_VERSION}", '
                    '"init": true, "depends_on": ["s4l-core"]}, "s4l-core": '
                    '{"image": '
                    '"${SIMCORE_REGISTRY}/simcore/services/dynamic/s4l-core:${SERVICE_VERSION}", '
                    '"runtime": "nvidia", "init": true, "environment": '
                    '["DISPLAY=${DISPLAY}"], "volumes": '
                    '["/tmp/.X11-unix:/tmp/.X11-unix"]}}}',
                    "container_http_entry": "rt-web",
                    "hostname": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "port": 1222,
                    "run_id": f"{run_id}",
                    "dynamic_sidecar": {
                        "containers_inspect": [],
                        "dynamic_sidecar_id": None,
                        "dynamic_sidecar_network_id": None,
                        "is_ready": False,
                        "is_project_network_attached": False,
                        "is_service_environment_ready": False,
                        "service_removal_state": {
                            "can_remove": False,
                            "can_save": None,
                            "was_removed": False,
                        },
                        "status": {"current": "ok", "info": ""},
                        "swarm_network_id": None,
                        "swarm_network_name": None,
                        "docker_node_id": None,
                        "was_compose_spec_submitted": False,
                        "was_dynamic_sidecar_started": False,
                        "were_containers_created": False,
                    },
                    "dynamic_sidecar_network_name": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "key": "simcore/services/dynamic/3dviewer",
                    "node_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "paths_mapping": {
                        "inputs_path": "/tmp/inputs",
                        "outputs_path": "/tmp/outputs",
                        "state_exclude": ["/tmp/strip_me/*", "*.py"],
                        "state_paths": ["/tmp/save_1", "/tmp_save_2"],
                    },
                    "project_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                    "proxy_service_name": "dy-proxy_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "request_dns": "test-endpoint",
                    "request_scheme": "http",
                    "restart_policy": "on-inputs-downloaded",
                    "service_name": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "service_port": 65534,
                    "service_resources": {
                        "container": {
                            "image": "simcore/services/dynamic/jupyter-math:2.0.5",
                            "resources": {
                                "CPU": {"limit": 0.1, "reservation": 0.1},
                                "RAM": {"limit": 2147483648, "reservation": 2147483648},
                            },
                        }
                    },
                    "simcore_traefik_zone": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "user_id": 234,
                    "version": "2.4.5",
                }
            ).as_label_data(),
            "port": "8888",
            "service_image": "local/dynamic-sidecar:MOCK",
            "service_port": "8888",
            "study_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
            "swarm_stack_name": "test_swarm_name",
            "type": "main-v2",
            "user_id": "234",
            "uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
        },
        "name": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
        "networks": [{"Target": "mocked_swarm_network_id"}],
        "task_template": {
            "ContainerSpec": {
                "Env": {
                    "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "DY_SIDECAR_NODE_ID": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "DY_SIDECAR_RUN_ID": f"{run_id}",
                    "DY_SIDECAR_PATH_INPUTS": "/tmp/inputs",
                    "DY_SIDECAR_PATH_OUTPUTS": "/tmp/outputs",
                    "DY_SIDECAR_PROJECT_ID": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                    "DY_SIDECAR_STATE_EXCLUDE": json_dumps({"*.py", "/tmp/strip_me/*"}),
                    "DY_SIDECAR_STATE_PATHS": json_dumps(
                        ["/tmp/save_1", "/tmp_save_2"]
                    ),
                    "DY_SIDECAR_USER_ID": "234",
                    "FORWARD_ENV_DISPLAY": ":0",
                    "DYNAMIC_SIDECAR_LOG_LEVEL": "DEBUG",
                    "POSTGRES_DB": "test",
                    "POSTGRES_HOST": "localhost",
                    "POSTGRES_PORT": "5432",
                    "POSTGRES_USER": "test",
                    "POSTGRES_PASSWORD": "test",
                    "POSTGRES_ENDPOINT": "localhost:5432",
                    "RABBIT_HOST": "rabbit",
                    "RABBIT_PASSWORD": "adminadmin",
                    "RABBIT_PORT": "5672",
                    "RABBIT_USER": "admin",
                    "REGISTRY_AUTH": "False",
                    "REGISTRY_PATH": "None",
                    "REGISTRY_PW": "test",
                    "REGISTRY_SSL": "False",
                    "REGISTRY_URL": "foo.bar.com",
                    "REGISTRY_USER": "test",
                    "R_CLONE_PROVIDER": "MINIO",
                    "R_CLONE_ENABLED": "False",
                    "S3_ACCESS_KEY": "12345678",
                    "S3_BUCKET_NAME": "simcore",
                    "S3_ENDPOINT": "http://172.17.0.1:9001",
                    "S3_SECRET_KEY": "12345678",
                    "S3_SECURE": "False",
                    "SC_BOOT_MODE": "production",
                    "SIMCORE_HOST_NAME": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "SSL_CERT_FILE": "",
                    "STORAGE_HOST": "storage",
                    "STORAGE_PORT": "8080",
                },
                "Hosts": [],
                "Image": "local/dynamic-sidecar:MOCK",
                "Init": True,
                "Labels": {
                    "mem_limit": "8589934592",
                    "nano_cpus_limit": "4000000000",
                    "study_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                    "user_id": "234",
                    "uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                },
                "Mounts": [
                    {
                        "Source": "/var/run/docker.sock",
                        "Target": "/var/run/docker.sock",
                        "Type": "bind",
                    },
                    {
                        "Source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_erots-derahs_",
                        "Target": "/dy-volumes/shared-store",
                        "Type": "volume",
                        "VolumeOptions": {
                            "Labels": {
                                "node_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                                "study_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                                "run_id": f"{run_id}",
                                "source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_erots-derahs_",
                                "swarm_stack_name": "test_swarm_name",
                                "user_id": "234",
                            }
                        },
                    },
                    {
                        "Target": "/dy-volumes/tmp/inputs",
                        "Source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_stupni_pmt_",
                        "Type": "volume",
                        "VolumeOptions": {
                            "Labels": {
                                "node_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                                "study_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                                "run_id": f"{run_id}",
                                "source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_stupni_pmt_",
                                "swarm_stack_name": "test_swarm_name",
                                "user_id": "234",
                            }
                        },
                    },
                    {
                        "Target": "/dy-volumes/tmp/outputs",
                        "Source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_stuptuo_pmt_",
                        "Type": "volume",
                        "VolumeOptions": {
                            "Labels": {
                                "node_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                                "study_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                                "run_id": f"{run_id}",
                                "source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_stuptuo_pmt_",
                                "swarm_stack_name": "test_swarm_name",
                                "user_id": "234",
                            }
                        },
                    },
                    {
                        "Target": "/dy-volumes/tmp/save_1",
                        "Source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_1_evas_pmt_",
                        "Type": "volume",
                        "VolumeOptions": {
                            "Labels": {
                                "node_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                                "study_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                                "run_id": f"{run_id}",
                                "source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_1_evas_pmt_",
                                "swarm_stack_name": "test_swarm_name",
                                "user_id": "234",
                            }
                        },
                    },
                    {
                        "Target": "/dy-volumes/tmp_save_2",
                        "Source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_2_evas_pmt_",
                        "Type": "volume",
                        "VolumeOptions": {
                            "Labels": {
                                "node_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                                "study_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                                "run_id": f"{run_id}",
                                "source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_2_evas_pmt_",
                                "swarm_stack_name": "test_swarm_name",
                                "user_id": "234",
                            }
                        },
                    },
                    {
                        "ReadOnly": True,
                        "Source": "/tmp/.X11-unix",
                        "Target": "/tmp/.X11-unix",
                        "Type": "bind",
                    },
                ],
            },
            "Placement": {"Constraints": ["node.platform.os == linux"]},
            "Resources": {
                "Limits": {"MemoryBytes": 8589934592, "NanoCPUs": 4000000000},
                "Reservations": {
                    "GenericResources": [
                        {"DiscreteResourceSpec": {"Kind": "VRAM", "Value": 1}}
                    ],
                    "MemoryBytes": 536870912,
                    "NanoCPUs": 100000000,
                },
            },
            "RestartPolicy": {
                "Condition": "on-failure",
                "Delay": 5000000000,
                "MaxAttempts": 0,
            },
        },
    }


def test_get_dynamic_proxy_spec(
    mocked_catalog_service_api: respx.MockRouter,
    minimal_app: FastAPI,
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    swarm_network_id: str,
    simcore_service_labels: SimcoreServiceLabels,
    expected_dynamic_sidecar_spec: dict[str, Any],
) -> None:
    dynamic_sidecar_spec_accumulated = None

    assert (
        dynamic_sidecar_settings.dict()
        == minimal_app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.dict()
    )
    expected_dynamic_sidecar_spec_model = AioDockerServiceSpec.parse_obj(
        expected_dynamic_sidecar_spec
    )
    assert expected_dynamic_sidecar_spec_model.TaskTemplate
    assert expected_dynamic_sidecar_spec_model.TaskTemplate.ContainerSpec
    assert expected_dynamic_sidecar_spec_model.TaskTemplate.ContainerSpec.Env

    for count in range(1, 11):  # loop to check it does not repeat copies
        print(f"{count:*^50}")

        dynamic_sidecar_spec: AioDockerServiceSpec = get_dynamic_sidecar_spec(
            scheduler_data=scheduler_data,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            swarm_network_id=swarm_network_id,
            settings=cast(SimcoreServiceSettingsLabel, simcore_service_labels.settings),
            app_settings=minimal_app.state.settings,
            has_quota_support=False,
        )

        # NOTE:
        exclude_keys = {
            "Labels": True,
            "TaskTemplate": {"ContainerSpec": {"Env": True}},
        }

        # NOTE: some flakiness here
        # state_exclude is a set and does not preserve order
        # when dumping to json it gets converted to a list
        dynamic_sidecar_spec.TaskTemplate.ContainerSpec.Env[
            "DY_SIDECAR_STATE_EXCLUDE"
        ] = sorted(
            dynamic_sidecar_spec.TaskTemplate.ContainerSpec.Env[
                "DY_SIDECAR_STATE_EXCLUDE"
            ]
        )
        expected_dynamic_sidecar_spec_model.TaskTemplate.ContainerSpec.Env[
            "DY_SIDECAR_STATE_EXCLUDE"
        ] = sorted(
            expected_dynamic_sidecar_spec_model.TaskTemplate.ContainerSpec.Env[
                "DY_SIDECAR_STATE_EXCLUDE"
            ]
        )

        assert dynamic_sidecar_spec.dict(
            exclude=exclude_keys
        ) == expected_dynamic_sidecar_spec_model.dict(exclude=exclude_keys)

        assert (
            dynamic_sidecar_spec.Labels.keys()
            == expected_dynamic_sidecar_spec_model.Labels.keys()
        )

        assert (
            dynamic_sidecar_spec.Labels["io.simcore.scheduler-data"]
            == expected_dynamic_sidecar_spec_model.Labels["io.simcore.scheduler-data"]
        )

        assert dynamic_sidecar_spec.Labels == expected_dynamic_sidecar_spec_model.Labels

        dynamic_sidecar_spec_accumulated = dynamic_sidecar_spec

    # check reference after multiple runs
    assert dynamic_sidecar_spec_accumulated is not None
    assert (
        dynamic_sidecar_spec_accumulated.dict()
        == expected_dynamic_sidecar_spec_model.dict()
    )
    # TODO: finish test when working on https://github.com/ITISFoundation/osparc-simcore/issues/2454


async def test_merge_dynamic_sidecar_specs_with_user_specific_specs(
    mocked_catalog_service_api: respx.MockRouter,
    minimal_app: FastAPI,
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    swarm_network_id: str,
    simcore_service_labels: SimcoreServiceLabels,
    expected_dynamic_sidecar_spec: dict[str, Any],
    mock_service_key_version: ServiceKeyVersion,
    fake_service_specifications: dict[str, Any],
):
    dynamic_sidecar_spec: AioDockerServiceSpec = get_dynamic_sidecar_spec(
        scheduler_data=scheduler_data,
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        swarm_network_id=swarm_network_id,
        settings=cast(SimcoreServiceSettingsLabel, simcore_service_labels.settings),
        app_settings=minimal_app.state.settings,
        has_quota_support=False,
    )
    assert dynamic_sidecar_spec
    dynamic_sidecar_spec_dict = dynamic_sidecar_spec.dict()
    expected_dynamic_sidecar_spec_dict = AioDockerServiceSpec.parse_obj(
        expected_dynamic_sidecar_spec
    ).dict()
    # ensure some entries are sorted the same to prevent flakyness
    for sorted_dict in [dynamic_sidecar_spec_dict, expected_dynamic_sidecar_spec_dict]:
        for key in ["DY_SIDECAR_STATE_EXCLUDE", "DY_SIDECAR_STATE_PATHS"]:
            # this is a json of a list
            assert isinstance(
                sorted_dict["TaskTemplate"]["ContainerSpec"]["Env"][key], str
            )
            unsorted_list = json.loads(
                sorted_dict["TaskTemplate"]["ContainerSpec"]["Env"][key]
            )
            assert isinstance(unsorted_list, list)
            sorted_dict["TaskTemplate"]["ContainerSpec"]["Env"][key] = json.dumps(
                unsorted_list.sort()
            )
    assert dynamic_sidecar_spec_dict == expected_dynamic_sidecar_spec_dict

    catalog_client = CatalogClient.instance(minimal_app)
    user_service_specs: dict[
        str, Any
    ] = await catalog_client.get_service_specifications(
        scheduler_data.user_id,
        mock_service_key_version.key,
        mock_service_key_version.version,
    )
    assert user_service_specs
    assert "sidecar" in user_service_specs
    user_aiodocker_service_spec = AioDockerServiceSpec.parse_obj(
        user_service_specs["sidecar"]
    )
    assert user_aiodocker_service_spec

    orig_dict = dynamic_sidecar_spec.dict(by_alias=True, exclude_unset=True)
    user_dict = user_aiodocker_service_spec.dict(by_alias=True, exclude_unset=True)

    another_merged_dict = nested_update(
        orig_dict,
        user_dict,
        include=(
            ["labels"],
            ["task_template", "Resources", "Limits"],
            ["task_template", "Resources", "Reservation", "MemoryBytes"],
            ["task_template", "Resources", "Reservation", "NanoCPUs"],
            ["task_template", "Placement", "Constraints"],
            ["task_template", "ContainerSpec", "Env"],
            ["task_template", "Resources", "Reservation", "GenericResources"],
        ),
    )
    assert another_merged_dict
