# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument


from typing import Any, cast
from uuid import UUID

import pytest
import respx
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.aiodocker_api import AioDockerServiceSpec
from models_library.service_settings_labels import (
    SimcoreServiceLabels,
    SimcoreServiceSettingsLabel,
)
from models_library.services import ServiceKeyVersion
from pytest import MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_service_director_v2.core.settings import DynamicSidecarSettings
from simcore_service_director_v2.models.schemas.dynamic_services import SchedulerData
from simcore_service_director_v2.modules.catalog import CatalogClient
from simcore_service_director_v2.modules.dynamic_sidecar.docker_service_specs import (
    get_dynamic_sidecar_spec,
)
from simcore_service_director_v2.utils.dict_utils import nested_update

# FIXTURES


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
def dynamic_sidecar_network_id() -> str:
    return "mocked_dynamic_sidecar_network_id"


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
def run_id(scheduler_data: SchedulerData) -> UUID:
    return scheduler_data.dynamic_sidecar.run_id


@pytest.fixture
def expected_dynamic_sidecar_spec(run_id: UUID) -> dict[str, Any]:
    return {
        "endpoint_spec": {},
        "labels": {
            "io.simcore.scheduler-data": '{"paths_mapping": {"inputs_path": '
            '"/tmp/inputs", "outputs_path": '
            '"/tmp/outputs", "state_paths": '
            '["/tmp/save_1", "/tmp_save_2"], '
            '"state_exclude": ["/tmp/strip_me/*", '
            '"*.py"]}, "compose_spec": '
            '"{\\"version\\": \\"2.3\\", '
            '\\"services\\": {\\"rt-web\\": '
            '{\\"image\\": '
            '\\"${SIMCORE_REGISTRY}/simcore/services/dynamic/sim4life:${SERVICE_VERSION}\\", '
            '\\"init\\": true, \\"depends_on\\": '
            '[\\"s4l-core\\"]}, \\"s4l-core\\": '
            '{\\"image\\": '
            '\\"${SIMCORE_REGISTRY}/simcore/services/dynamic/s4l-core:${SERVICE_VERSION}\\", '
            '\\"runtime\\": \\"nvidia\\", '
            '\\"init\\": true, \\"environment\\": '
            '[\\"DISPLAY=${DISPLAY}\\"], '
            '\\"volumes\\": '
            '[\\"/tmp/.X11-unix:/tmp/.X11-unix\\"]}}}", '
            '"container_http_entry": "rt-web", '
            '"restart_policy": '
            '"on-inputs-downloaded", "key": '
            '"simcore/services/dynamic/3dviewer", '
            '"version": "2.4.5", "user_id": 234, '
            '"project_id": '
            '"dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe", '
            '"node_uuid": '
            '"75c7f3f4-18f9-4678-8610-54a2ade78eaa", '
            '"service_name": '
            '"dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa", '
            '"dynamic_sidecar": {'
            f'"run_id": "{run_id}", '
            '"status": '
            '{"current": "ok", "info": ""}, '
            '"hostname": '
            '"dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa", '
            '"port": 1222, "is_available": false, '
            '"was_compose_spec_submitted": false, '
            '"containers_inspect": [], '
            '"was_dynamic_sidecar_started": '
            'false, "were_services_created": '
            "false, "
            '"is_project_network_attached": '
            "false, "
            '"service_environment_prepared": '
            'false, "service_removal_state": '
            '{"can_remove": false, "can_save": '
            'null, "was_removed": false}, '
            '"dynamic_sidecar_id": null, '
            '"dynamic_sidecar_network_id": null, '
            '"swarm_network_id": null, '
            '"swarm_network_name": null}, '
            '"dynamic_sidecar_network_name": '
            '"dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa", '
            '"simcore_traefik_zone": '
            '"dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa", '
            '"service_port": 65534, '
            '"service_resources": {"container": {"image": '
            '"simcore/services/dynamic/jupyter-math:2.0.5", "resources": '
            '{"CPU": {"limit": 0.1, "reservation": 0.1}, "RAM": '
            '{"limit": 2147483648, "reservation": 2147483648}}}}, '
            '"request_dns": null, '
            '"request_scheme": null, '
            '"proxy_service_name": '
            '"dy-proxy_75c7f3f4-18f9-4678-8610-54a2ade78eaa"}',
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
        "networks": [
            {"Target": "mocked_swarm_network_id"},
            {"Target": "mocked_dynamic_sidecar_network_id"},
        ],
        "task_template": {
            "ContainerSpec": {
                "Env": {
                    "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "DY_SIDECAR_NODE_ID": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "DY_SIDECAR_RUN_ID": f"{run_id}",
                    "DY_SIDECAR_PATH_INPUTS": "/tmp/inputs",
                    "DY_SIDECAR_PATH_OUTPUTS": "/tmp/outputs",
                    "DY_SIDECAR_PROJECT_ID": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                    "DY_SIDECAR_STATE_EXCLUDE": '["/tmp/strip_me/*", ' '"*.py"]',
                    "DY_SIDECAR_STATE_PATHS": '["/tmp/save_1", ' '"/tmp_save_2"]',
                    "DY_SIDECAR_USER_ID": "234",
                    "FORWARD_ENV_DISPLAY": ":0",
                    "LOG_LEVEL": "DEBUG",
                    "POSTGRES_DB": "test",
                    "POSTGRES_HOST": "localhost",
                    "POSTGRES_PORT": "5432",
                    "POSTGRES_USER": "test",
                    "POSTGRES_PASSWORD": "test",
                    "POSTGRES_ENDPOINT": "localhost:5432",
                    "RABBIT_CHANNELS": '{"log": '
                    '"simcore.services.logs", '
                    '"progress": '
                    '"simcore.services.progress", '
                    '"instrumentation": '
                    '"simcore.services.instrumentation", '
                    '"events": '
                    '"simcore.services.events"}',
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
                    "R_CLONE_ENABLED": "True",
                    "S3_ACCESS_KEY": "12345678",
                    "S3_BUCKET_NAME": "simcore",
                    "S3_ENDPOINT": "http://172.17.0.1:9001",
                    "S3_SECRET_KEY": "12345678",
                    "S3_SECURE": "False",
                    "SC_BOOT_MODE": "production",
                    "SIMCORE_HOST_NAME": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "STORAGE_HOST": "storage",
                    "STORAGE_PORT": "8080",
                },
                "Hosts": [],
                "Image": "local/dynamic-sidecar:MOCK",
                "Init": True,
                "Labels": {"mem_limit": "8589934592", "nano_cpus_limit": "4000000000"},
                "Mounts": [
                    {
                        "Source": "/var/run/docker.sock",
                        "Target": "/var/run/docker.sock",
                        "Type": "bind",
                    },
                    {
                        "Target": "/dy-volumes/tmp/inputs",
                        "Type": "volume",
                        "VolumeOptions": {
                            "Labels": {
                                "run_id": f"{run_id}",
                                "source": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa_tmp_inputs",
                                "swarm_stack_name": "test_swarm_name",
                                "uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                            }
                        },
                    },
                    {
                        "Target": "/dy-volumes/tmp/outputs",
                        "Type": "volume",
                        "VolumeOptions": {
                            "Labels": {
                                "run_id": f"{run_id}",
                                "source": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa_tmp_outputs",
                                "swarm_stack_name": "test_swarm_name",
                                "uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                            }
                        },
                    },
                    {
                        "Target": "/dy-volumes/tmp/save_1",
                        "Type": "volume",
                        "VolumeOptions": {
                            "Labels": {
                                "run_id": f"{run_id}",
                                "source": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa_tmp_save_1",
                                "swarm_stack_name": "test_swarm_name",
                                "uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                            }
                        },
                    },
                    {
                        "Target": "/dy-volumes/tmp_save_2",
                        "Type": "volume",
                        "VolumeOptions": {
                            "Labels": {
                                "run_id": f"{run_id}",
                                "source": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa_tmp_save_2",
                                "swarm_stack_name": "test_swarm_name",
                                "uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
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
                "Delay": 5000000,
                "MaxAttempts": 2,
            },
        },
    }


# TESTS


def test_get_dynamic_proxy_spec(
    mocked_catalog_service_api: respx.MockRouter,
    minimal_app: FastAPI,
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_network_id: str,
    swarm_network_id: str,
    simcore_service_labels: SimcoreServiceLabels,
    expected_dynamic_sidecar_spec: dict[str, Any],
) -> None:
    dynamic_sidecar_spec_accumulated = None

    assert (
        dynamic_sidecar_settings.dict()
        == minimal_app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.dict()
    )

    for count in range(1, 11):  # loop to check it does not repeat copies
        print(f"{count:*^50}")
        dynamic_sidecar_spec = get_dynamic_sidecar_spec(
            scheduler_data=scheduler_data,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            dynamic_sidecar_network_id=dynamic_sidecar_network_id,
            swarm_network_id=swarm_network_id,
            settings=cast(SimcoreServiceSettingsLabel, simcore_service_labels.settings),
            app_settings=minimal_app.state.settings,
        )
        assert dynamic_sidecar_spec
        assert (
            jsonable_encoder(dynamic_sidecar_spec, by_alias=True, exclude_unset=True)
            == expected_dynamic_sidecar_spec
        )
        dynamic_sidecar_spec_accumulated = dynamic_sidecar_spec
    assert (
        jsonable_encoder(
            dynamic_sidecar_spec_accumulated, by_alias=True, exclude_unset=True
        )
        == expected_dynamic_sidecar_spec
    )
    # TODO: finish test when working on https://github.com/ITISFoundation/osparc-simcore/issues/2454


async def test_merge_dynamic_sidecar_specs_with_user_specific_specs(
    mocked_catalog_service_api: respx.MockRouter,
    minimal_app: FastAPI,
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_network_id: str,
    swarm_network_id: str,
    simcore_service_labels: SimcoreServiceLabels,
    expected_dynamic_sidecar_spec: dict[str, Any],
    mock_service_key_version: ServiceKeyVersion,
    fake_service_specifications: dict[str, Any],
):
    dynamic_sidecar_spec: AioDockerServiceSpec = get_dynamic_sidecar_spec(
        scheduler_data=scheduler_data,
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        dynamic_sidecar_network_id=dynamic_sidecar_network_id,
        swarm_network_id=swarm_network_id,
        settings=cast(SimcoreServiceSettingsLabel, simcore_service_labels.settings),
        app_settings=minimal_app.state.settings,
    )
    assert dynamic_sidecar_spec
    assert (
        jsonable_encoder(dynamic_sidecar_spec, by_alias=True, exclude_unset=True)
        == expected_dynamic_sidecar_spec
    )

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
