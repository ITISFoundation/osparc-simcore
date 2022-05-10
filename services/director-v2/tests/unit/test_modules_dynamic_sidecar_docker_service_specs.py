# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

from pprint import pprint
from typing import Any, Dict, Iterator, cast

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi import FastAPI
from models_library.service_settings_labels import (
    SimcoreServiceLabels,
    SimcoreServiceSettingsLabel,
)
from simcore_service_director_v2.core.settings import DynamicSidecarSettings
from simcore_service_director_v2.models.schemas.dynamic_services import SchedulerData
from simcore_service_director_v2.modules.dynamic_sidecar.docker_service_specs import (
    get_dynamic_sidecar_spec,
)

# FIXTURES


@pytest.fixture
def mocked_env(monkeypatch: MonkeyPatch) -> Iterator[Dict[str, str]]:
    env_vars: Dict[str, str] = {
        "REGISTRY_AUTH": "false",
        "REGISTRY_USER": "test",
        "REGISTRY_PW": "test",
        "REGISTRY_SSL": "false",
        "DYNAMIC_SIDECAR_IMAGE": "local/dynamic-sidecar:MOCK",
        "POSTGRES_HOST": "test_host",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_password",
        "POSTGRES_DB": "test_db",
        "SIMCORE_SERVICES_NETWORK_NAME": "simcore_services_network_name",
        "TRAEFIK_SIMCORE_ZONE": "test_traefik_zone",
        "SWARM_STACK_NAME": "test_swarm_name",
        "R_CLONE_PROVIDER": "MINIO",
        "S3_ENDPOINT": "endpoint",
        "S3_ACCESS_KEY": "access_key",
        "S3_SECRET_KEY": "secret_key",
        "S3_BUCKET_NAME": "bucket_name",
        "S3_SECURE": "false",
    }

    with monkeypatch.context() as m:
        for key, value in env_vars.items():
            m.setenv(key, value)

        yield env_vars


@pytest.fixture
def dynamic_sidecar_settings(mocked_env: Dict[str, str]) -> DynamicSidecarSettings:
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
    return SimcoreServiceLabels(
        **SimcoreServiceLabels.Config.schema_extra["examples"][2]
    )


@pytest.fixture
def minimal_catalog_config(project_env_devel_environment, monkeypatch):
    """set a minimal configuration for testing the director connection only"""


@pytest.fixture
def expected_dynamic_sidecar_spec() -> dict[str, Any]:
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
            '\\"${REGISTRY_URL}/simcore/services/dynamic/sim4life:${SERVICE_TAG}\\", '
            '\\"init\\": true, \\"depends_on\\": '
            '[\\"s4l-core\\"]}, \\"s4l-core\\": '
            '{\\"image\\": '
            '\\"${REGISTRY_URL}/simcore/services/dynamic/s4l-core:${SERVICE_TAG}\\", '
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
            '"dynamic_sidecar": {"status": '
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
            '"request_dns": null, '
            '"request_scheme": null, '
            '"proxy_service_name": '
            '"dy-proxy_75c7f3f4-18f9-4678-8610-54a2ade78eaa"}',
            "io.simcore.zone": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
            "port": "8000",
            "service_image": "local/dynamic-sidecar:MOCK",
            "study_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
            "swarm_stack_name": "test_swarm_name",
            "traefik.docker.network": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
            "traefik.enable": "true",
            "traefik.http.routers.dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa.entrypoints": "http",
            "traefik.http.routers.dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa.priority": "10",
            "traefik.http.routers.dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa.rule": "PathPrefix(`/`)",
            "traefik.http.services.dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa.loadbalancer.server.port": "8000",
            "type": "main-v2",
            "user_id": "234",
            "uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
        },
        "name": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
        "networks": ["mocked_swarm_network_id", "mocked_dynamic_sidecar_network_id"],
        "task_template": {
            "ContainerSpec": {
                "Env": {
                    "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "DY_SIDECAR_NODE_ID": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "DY_SIDECAR_PATH_INPUTS": "/tmp/inputs",
                    "DY_SIDECAR_PATH_OUTPUTS": "/tmp/outputs",
                    "DY_SIDECAR_PROJECT_ID": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                    "DY_SIDECAR_STATE_EXCLUDE": '["/tmp/strip_me/*", ' '"*.py"]',
                    "DY_SIDECAR_STATE_PATHS": '["/tmp/save_1", ' '"/tmp_save_2"]',
                    "DY_SIDECAR_USER_ID": "234",
                    "FORWARD_ENV_DISPLAY": ":0",
                    "LOG_LEVEL": "WARNING",
                    "POSTGRES_DB": "mocked_db",
                    "POSTGRES_ENDPOINT": "mocked_host:5432",
                    "POSTGRES_HOST": "mocked_host",
                    "POSTGRES_PASSWORD": "mocked_password",
                    "POSTGRES_PORT": "5432",
                    "POSTGRES_USER": "mocked_user",
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
                    "REGISTRY_URL": "registry.osparc-master.speag.com",
                    "REGISTRY_USER": "test",
                    "R_CLONE_PROVIDER": "MINIO",
                    "S3_ACCESS_KEY": "12345678",
                    "S3_BUCKET_NAME": "simcore",
                    "S3_ENDPOINT": "http://172.17.0.1:9001",
                    "S3_SECRET_KEY": "12345678",
                    "S3_SECURE": "False",
                    "SIMCORE_HOST_NAME": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "STORAGE_ENDPOINT": "storage:8080",
                },
                "Hosts": [],
                "Image": "local/dynamic-sidecar:MOCK",
                "Init": True,
                "Labels": {"mem_limit": "17179869184", "nano_cpus_limit": "4000000000"},
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
                "Limits": {"MemoryBytes": 17179869184, "NanoCPUs": 4000000000},
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
    minimal_catalog_config: None,
    minimal_app: FastAPI,
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_network_id: str,
    swarm_network_id: str,
    simcore_service_labels: SimcoreServiceLabels,
    expected_dynamic_sidecar_spec: dict[str, Any],
) -> None:
    dynamic_sidecar_spec = get_dynamic_sidecar_spec(
        scheduler_data=scheduler_data,
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        dynamic_sidecar_network_id=dynamic_sidecar_network_id,
        swarm_network_id=swarm_network_id,
        settings=cast(SimcoreServiceSettingsLabel, simcore_service_labels.settings),
        app_settings=minimal_app.state.settings,
    )
    assert dynamic_sidecar_spec
    assert dynamic_sidecar_spec == expected_dynamic_sidecar_spec
    pprint(dynamic_sidecar_spec)
    # TODO: finish test when working on https://github.com/ITISFoundation/osparc-simcore/issues/2454


def test_merge_user_specific_and_dynamic_sidecar_specs(
    minimal_catalog_config: None,
    minimal_app: FastAPI,
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_network_id: str,
    swarm_network_id: str,
    simcore_service_labels: SimcoreServiceLabels,
    expected_dynamic_sidecar_spec: dict[str, Any],
):
    dynamic_sidecar_spec = get_dynamic_sidecar_spec(
        scheduler_data=scheduler_data,
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        dynamic_sidecar_network_id=dynamic_sidecar_network_id,
        swarm_network_id=swarm_network_id,
        settings=cast(SimcoreServiceSettingsLabel, simcore_service_labels.settings),
        app_settings=minimal_app.state.settings,
    )
    assert dynamic_sidecar_spec
    assert dynamic_sidecar_spec == expected_dynamic_sidecar_spec
