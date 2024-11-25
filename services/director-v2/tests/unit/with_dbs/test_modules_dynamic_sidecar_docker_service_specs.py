# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument


import json
from typing import Any, cast
from unittest.mock import Mock

import pytest
import respx
from common_library.json_serialization import json_dumps
from faker import Faker
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.aiodocker_api import AioDockerServiceSpec
from models_library.callbacks_mapping import CallbacksMapping
from models_library.docker import (
    DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY,
    to_simcore_runtime_docker_label_key,
)
from models_library.resource_tracker import HardwareInfo, PricingInfo
from models_library.service_settings_labels import (
    SimcoreServiceLabels,
    SimcoreServiceSettingsLabel,
)
from models_library.services import RunID, ServiceKeyVersion
from models_library.wallets import WalletInfo
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.s3 import S3Settings
from simcore_service_director_v2.core.dynamic_services_settings.scheduler import (
    DynamicServicesSchedulerSettings,
)
from simcore_service_director_v2.core.dynamic_services_settings.sidecar import (
    DynamicSidecarSettings,
)
from simcore_service_director_v2.models.dynamic_services_scheduler import SchedulerData
from simcore_service_director_v2.modules.catalog import CatalogClient
from simcore_service_director_v2.modules.db.repositories.groups_extra_properties import (
    UserExtraProperties,
)
from simcore_service_director_v2.modules.dynamic_sidecar.docker_service_specs import (
    get_dynamic_sidecar_spec,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._event_create_sidecars import (
    _DYNAMIC_SIDECAR_SERVICE_EXTENDABLE_SPECS,
    _merge_service_base_and_user_specs,
)
from simcore_service_director_v2.utils.dict_utils import nested_update


@pytest.fixture
def mock_s3_settings() -> S3Settings:
    return S3Settings.model_validate(
        S3Settings.model_config["json_schema_extra"]["examples"][0]
    )


@pytest.fixture
def mock_env(
    monkeypatch: pytest.MonkeyPatch,
    mock_env: EnvVarsDict,
    disable_postgres: None,
    mock_s3_settings: S3Settings,
    faker: Faker,
) -> EnvVarsDict:
    """overrides unit/conftest:mock_env fixture"""
    env_vars = mock_env.copy()
    env_vars.update(
        {
            "AWS_S3_CLI_S3": '{"S3_ACCESS_KEY":"12345678","S3_BUCKET_NAME":"simcore","S3_ENDPOINT":"http://172.17.0.1:9001","S3_REGION":"us-east-1","S3_SECRET_KEY":"12345678"}',
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
            "RABBIT_SECURE": "false",
            "REGISTRY_AUTH": "false",
            "REGISTRY_PW": "test",
            "REGISTRY_SSL": "false",
            "REGISTRY_URL": "foo.bar.com",
            "REGISTRY_USER": "test",
            "SC_BOOT_MODE": "production",
            "SIMCORE_SERVICES_NETWORK_NAME": "simcore_services_network_name",
            "SWARM_STACK_NAME": "test_swarm_name",
            "TRAEFIK_SIMCORE_ZONE": "test_traefik_zone",
            **jsonable_encoder(mock_s3_settings, exclude_none=True),
        }
    )
    setenvs_from_dict(monkeypatch, env_vars)
    return env_vars


@pytest.fixture
def dynamic_sidecar_settings(mock_env: dict[str, str]) -> DynamicSidecarSettings:
    return DynamicSidecarSettings.create_from_envs()


@pytest.fixture
def dynamic_services_scheduler_settings(
    mock_env: dict[str, str],
) -> DynamicServicesSchedulerSettings:
    return DynamicServicesSchedulerSettings.create_from_envs()


@pytest.fixture
def swarm_network_id() -> str:
    return "mocked_swarm_network_id"


@pytest.fixture
def simcore_service_labels() -> SimcoreServiceLabels:
    # overwrites global fixture
    return SimcoreServiceLabels.model_validate(
        SimcoreServiceLabels.model_config["json_schema_extra"]["examples"][2]
    )


@pytest.fixture
def hardware_info() -> HardwareInfo:
    return HardwareInfo.model_validate(
        HardwareInfo.model_config["json_schema_extra"]["examples"][0]
    )


@pytest.fixture
def expected_dynamic_sidecar_spec(
    run_id: RunID,
    osparc_product_name: str,
    request_simcore_user_agent: str,
    hardware_info: HardwareInfo,
    faker: Faker,
    mock_s3_settings: S3Settings,
) -> dict[str, Any]:
    return {
        "endpoint_spec": {},
        "labels": {
            "io.simcore.scheduler-data": SchedulerData.model_validate(
                {
                    "compose_spec": '{"version": "2.3", "services": {"rt-web": {"image": '
                    '"${SIMCORE_REGISTRY}/simcore/services/dynamic/sim4life:${SERVICE_VERSION}", '
                    '"init": true, "depends_on": ["s4l-core"], "storage_opt": {"size": "10M"} }, '
                    '"s4l-core": {"image": '
                    '"${SIMCORE_REGISTRY}/simcore/services/dynamic/s4l-core:${SERVICE_VERSION}", '
                    '"runtime": "nvidia", "storage_opt": {"size": "5G"}, "init": true, '
                    '"environment": ["DISPLAY=${DISPLAY}"], "volumes": '
                    '["/tmp/.X11-unix:/tmp/.X11-unix"]}}}',
                    "container_http_entry": "rt-web",
                    "hostname": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "port": 1222,
                    "run_id": run_id,
                    "dynamic_sidecar": {
                        "containers_inspect": [],
                        "dynamic_sidecar_id": None,
                        "dynamic_sidecar_network_id": None,
                        "is_ready": False,
                        "is_project_network_attached": False,
                        "is_service_environment_ready": False,
                        "service_removal_state": {
                            "can_remove": False,
                            "can_save": True,
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
                        "inputs_path": "/tmp/inputs",  # noqa: S108
                        "outputs_path": "/tmp/outputs",  # noqa: S108
                        "state_exclude": ["/tmp/strip_me/*"],  # noqa: S108
                        "state_paths": ["/tmp/save_1", "/tmp_save_2"],  # noqa: S108
                    },
                    "callbacks_mapping": CallbacksMapping.model_config[
                        "json_schema_extra"
                    ]["examples"][3],
                    "product_name": osparc_product_name,
                    "project_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                    "proxy_service_name": "dy-proxy_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "request_dns": "test-endpoint",
                    "request_scheme": "http",
                    "request_simcore_user_agent": request_simcore_user_agent,
                    "restart_policy": "on-inputs-downloaded",
                    "wallet_info": WalletInfo.model_config["json_schema_extra"][
                        "examples"
                    ][0],
                    "pricing_info": PricingInfo.model_config["json_schema_extra"][
                        "examples"
                    ][0],
                    "hardware_info": hardware_info,
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
            f"{to_simcore_runtime_docker_label_key('service-key')}": "simcore/services/dynamic/3dviewer",
            f"{to_simcore_runtime_docker_label_key('service-version')}": "2.4.5",
            f"{to_simcore_runtime_docker_label_key('memory-limit')}": "8589934592",
            f"{to_simcore_runtime_docker_label_key('cpu-limit')}": "4.0",
            f"{to_simcore_runtime_docker_label_key('project-id')}": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
            f"{to_simcore_runtime_docker_label_key('user-id')}": "234",
            f"{to_simcore_runtime_docker_label_key('node-id')}": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
            f"{to_simcore_runtime_docker_label_key('product-name')}": "osparc",
            f"{to_simcore_runtime_docker_label_key('simcore-user-agent')}": "python/test",
            f"{to_simcore_runtime_docker_label_key('swarm-stack-name')}": "test_swarm_name",
        },
        "name": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
        "networks": [{"Target": "mocked_swarm_network_id"}],
        "task_template": {
            "ContainerSpec": {
                "Env": {
                    "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "DY_SIDECAR_NODE_ID": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "DY_SIDECAR_RUN_ID": run_id,
                    "DY_SIDECAR_PATH_INPUTS": "/tmp/inputs",  # noqa: S108
                    "DY_SIDECAR_PATH_OUTPUTS": "/tmp/outputs",  # noqa: S108
                    "DY_SIDECAR_PROJECT_ID": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                    "DY_SIDECAR_STATE_EXCLUDE": json_dumps(
                        ["/tmp/strip_me/*"]  # noqa: S108
                    ),
                    "DY_SIDECAR_STATE_PATHS": json_dumps(
                        ["/tmp/save_1", "/tmp_save_2"]  # noqa: S108
                    ),
                    "DY_SIDECAR_USER_ID": "234",
                    "DY_SIDECAR_USER_SERVICES_HAVE_INTERNET_ACCESS": "False",
                    "DY_SIDECAR_SYSTEM_MONITOR_TELEMETRY_ENABLE": "True",
                    "FORWARD_ENV_DISPLAY": ":0",
                    "NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS": "3",
                    "DYNAMIC_SIDECAR_LOG_LEVEL": "DEBUG",
                    "DYNAMIC_SIDECAR_TRACING": "null",
                    "DY_DEPLOYMENT_REGISTRY_SETTINGS": (
                        '{"REGISTRY_AUTH":false,"REGISTRY_PATH":null,'
                        '"REGISTRY_URL":"foo.bar.com","REGISTRY_USER":'
                        '"test","REGISTRY_PW":"test","REGISTRY_SSL":false}'
                    ),
                    "DY_DOCKER_HUB_REGISTRY_SETTINGS": "null",
                    "DY_SIDECAR_AWS_S3_CLI_SETTINGS": (
                        '{"AWS_S3_CLI_S3":{"S3_ACCESS_KEY":"12345678","S3_BUCKET_NAME":"simcore",'
                        '"S3_ENDPOINT":"http://172.17.0.1:9001/","S3_REGION":"us-east-1","S3_SECRET_KEY":"12345678"}}'
                    ),
                    "DY_SIDECAR_CALLBACKS_MAPPING": (
                        '{"metrics":{"service":"rt-web","command":"ls","timeout":1.0},"before_shutdown"'
                        ':[{"service":"rt-web","command":"ls","timeout":1.0},{"service":"s4l-core",'
                        '"command":["ls","-lah"],"timeout":1.0}],"inactivity":null}'
                    ),
                    "DY_SIDECAR_SERVICE_KEY": "simcore/services/dynamic/3dviewer",
                    "DY_SIDECAR_SERVICE_VERSION": "2.4.5",
                    "DY_SIDECAR_PRODUCT_NAME": osparc_product_name,
                    "DY_SIDECAR_USER_PREFERENCES_PATH": "None",
                    "DY_SIDECAR_LOG_FORMAT_LOCAL_DEV_ENABLED": "True",
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
                    "RABBIT_SECURE": "False",
                    "R_CLONE_OPTION_BUFFER_SIZE": "0M",
                    "R_CLONE_OPTION_RETRIES": "3",
                    "R_CLONE_OPTION_TRANSFERS": "5",
                    "R_CLONE_PROVIDER": "MINIO",
                    "SC_BOOT_MODE": "production",
                    "SIMCORE_HOST_NAME": "dy-sidecar_75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "SSL_CERT_FILE": "",
                    "STORAGE_USERNAME": "null",
                    "STORAGE_HOST": "storage",
                    "STORAGE_PASSWORD": "null",
                    "STORAGE_SECURE": "0",
                    "STORAGE_PORT": "8080",
                    **jsonable_encoder(mock_s3_settings, exclude_unset=True),
                },
                "CapabilityAdd": None,
                "Hosts": [],
                "Image": "local/dynamic-sidecar:MOCK",
                "Init": True,
                "Labels": {
                    f"{to_simcore_runtime_docker_label_key('memory-limit')}": "8589934592",
                    f"{to_simcore_runtime_docker_label_key('cpu-limit')}": "4.0",
                    f"{to_simcore_runtime_docker_label_key('project-id')}": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                    f"{to_simcore_runtime_docker_label_key('user-id')}": "234",
                    f"{to_simcore_runtime_docker_label_key('node-id')}": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    f"{to_simcore_runtime_docker_label_key('product-name')}": "osparc",
                    f"{to_simcore_runtime_docker_label_key('simcore-user-agent')}": "python/test",
                    f"{to_simcore_runtime_docker_label_key('swarm-stack-name')}": "test_swarm_name",
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
                            "DriverConfig": None,
                            "Labels": {
                                "node_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                                "study_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                                "run_id": run_id,
                                "source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_erots-derahs_",
                                "swarm_stack_name": "test_swarm_name",
                                "user_id": "234",
                            },
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
                                "run_id": run_id,
                                "source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_stupni_pmt_",
                                "swarm_stack_name": "test_swarm_name",
                                "user_id": "234",
                            },
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
                                "run_id": run_id,
                                "source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_stuptuo_pmt_",
                                "swarm_stack_name": "test_swarm_name",
                                "user_id": "234",
                            },
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
                                "run_id": run_id,
                                "source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_1_evas_pmt_",
                                "swarm_stack_name": "test_swarm_name",
                                "user_id": "234",
                            },
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
                                "run_id": run_id,
                                "source": f"dyv_{run_id}_75c7f3f4-18f9-4678-8610-54a2ade78eaa_2_evas_pmt_",
                                "swarm_stack_name": "test_swarm_name",
                                "user_id": "234",
                            },
                        },
                    },
                    {
                        "ReadOnly": True,
                        "Source": "/tmp/.X11-unix",  # noqa: S108
                        "Target": "/tmp/.X11-unix",  # noqa: S108
                        "Type": "bind",
                    },
                ],
            },
            "Placement": {
                "Constraints": [
                    f"node.labels.{DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY}=={hardware_info.aws_ec2_instances[0]}",
                    "node.platform.os == linux",
                ]
            },
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


async def test_get_dynamic_proxy_spec(
    mocked_catalog_service_api: respx.MockRouter,
    minimal_app: FastAPI,
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
    swarm_network_id: str,
    simcore_service_labels: SimcoreServiceLabels,
    expected_dynamic_sidecar_spec: dict[str, Any],
    hardware_info: HardwareInfo,
) -> None:
    dynamic_sidecar_spec_accumulated = None

    assert (
        dynamic_sidecar_settings
        == minimal_app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
    )

    expected_dynamic_sidecar_spec_model = AioDockerServiceSpec.model_validate(
        expected_dynamic_sidecar_spec
    )
    assert expected_dynamic_sidecar_spec_model.task_template
    assert expected_dynamic_sidecar_spec_model.task_template.container_spec
    assert expected_dynamic_sidecar_spec_model.task_template.container_spec.env

    for count in range(1, 11):  # loop to check it does not repeat copies
        print(f"{count:*^50}")

        dynamic_sidecar_spec: AioDockerServiceSpec = await get_dynamic_sidecar_spec(
            scheduler_data=scheduler_data,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            dynamic_services_scheduler_settings=dynamic_services_scheduler_settings,
            swarm_network_id=swarm_network_id,
            settings=cast(SimcoreServiceSettingsLabel, simcore_service_labels.settings),
            app_settings=minimal_app.state.settings,
            hardware_info=hardware_info,
            has_quota_support=False,
            metrics_collection_allowed=True,
            user_extra_properties=UserExtraProperties(
                is_internet_enabled=False,
                is_telemetry_enabled=True,
                is_efs_enabled=False,
            ),
            rpc_client=Mock(),
        )

        exclude_keys = {
            "Labels": True,
            "TaskTemplate": {"ContainerSpec": {"Env": True}},
        }

        # NOTE: some flakiness here
        # state_exclude is a set and does not preserve order
        # when dumping to json it gets converted to a list
        assert dynamic_sidecar_spec.task_template
        assert dynamic_sidecar_spec.task_template.container_spec
        assert dynamic_sidecar_spec.task_template.container_spec.env
        assert dynamic_sidecar_spec.task_template.container_spec.env[
            "DY_SIDECAR_STATE_EXCLUDE"
        ]

        dynamic_sidecar_spec.task_template.container_spec.env[
            "DY_SIDECAR_STATE_EXCLUDE"
        ] = json.dumps(
            sorted(
                json.loads(
                    dynamic_sidecar_spec.task_template.container_spec.env[
                        "DY_SIDECAR_STATE_EXCLUDE"
                    ]
                )
            )
        )
        assert expected_dynamic_sidecar_spec_model.task_template.container_spec.env[
            "DY_SIDECAR_STATE_EXCLUDE"
        ]
        expected_dynamic_sidecar_spec_model.task_template.container_spec.env[
            "DY_SIDECAR_STATE_EXCLUDE"
        ] = json.dumps(
            sorted(
                json.loads(
                    expected_dynamic_sidecar_spec_model.task_template.container_spec.env[
                        "DY_SIDECAR_STATE_EXCLUDE"
                    ]
                )
            )
        )

        assert dynamic_sidecar_spec.model_dump(
            exclude=exclude_keys  # type: ignore[arg-type]
        ) == expected_dynamic_sidecar_spec_model.model_dump(
            exclude=exclude_keys  # type: ignore[arg-type]
        )
        assert dynamic_sidecar_spec.labels
        assert expected_dynamic_sidecar_spec_model.labels
        assert sorted(dynamic_sidecar_spec.labels.keys()) == sorted(
            expected_dynamic_sidecar_spec_model.labels.keys()
        )

        assert (
            dynamic_sidecar_spec.labels["io.simcore.scheduler-data"]
            == expected_dynamic_sidecar_spec_model.labels["io.simcore.scheduler-data"]
        )

        assert dynamic_sidecar_spec.labels == expected_dynamic_sidecar_spec_model.labels

        dynamic_sidecar_spec_accumulated = dynamic_sidecar_spec

    # check reference after multiple runs
    assert dynamic_sidecar_spec_accumulated is not None
    assert (
        dynamic_sidecar_spec_accumulated.model_dump()
        == expected_dynamic_sidecar_spec_model.model_dump()
    )


async def test_merge_dynamic_sidecar_specs_with_user_specific_specs(
    mocked_catalog_service_api: respx.MockRouter,
    minimal_app: FastAPI,
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
    swarm_network_id: str,
    simcore_service_labels: SimcoreServiceLabels,
    expected_dynamic_sidecar_spec: dict[str, Any],
    mock_service_key_version: ServiceKeyVersion,
    hardware_info: HardwareInfo,
    fake_service_specifications: dict[str, Any],
):
    dynamic_sidecar_spec: AioDockerServiceSpec = await get_dynamic_sidecar_spec(
        scheduler_data=scheduler_data,
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        dynamic_services_scheduler_settings=dynamic_services_scheduler_settings,
        swarm_network_id=swarm_network_id,
        settings=cast(SimcoreServiceSettingsLabel, simcore_service_labels.settings),
        app_settings=minimal_app.state.settings,
        hardware_info=hardware_info,
        has_quota_support=False,
        metrics_collection_allowed=True,
        user_extra_properties=UserExtraProperties(
            is_internet_enabled=False,
            is_telemetry_enabled=True,
            is_efs_enabled=False,
        ),
        rpc_client=Mock(),
    )
    assert dynamic_sidecar_spec
    dynamic_sidecar_spec_dict = dynamic_sidecar_spec.model_dump()
    expected_dynamic_sidecar_spec_dict = AioDockerServiceSpec.model_validate(
        expected_dynamic_sidecar_spec
    ).model_dump()
    # ensure some entries are sorted the same to prevent flakyness
    for sorted_dict in [dynamic_sidecar_spec_dict, expected_dynamic_sidecar_spec_dict]:
        for key in ["DY_SIDECAR_STATE_EXCLUDE", "DY_SIDECAR_STATE_PATHS"]:
            # this is a json of a list
            assert isinstance(
                sorted_dict["task_template"]["container_spec"]["env"][key], str
            )
            unsorted_list = json.loads(
                sorted_dict["task_template"]["container_spec"]["env"][key]
            )
            assert isinstance(unsorted_list, list)
            sorted_dict["task_template"]["container_spec"]["env"][key] = json.dumps(
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
    user_aiodocker_service_spec = AioDockerServiceSpec.model_validate(
        user_service_specs["sidecar"]
    )
    assert user_aiodocker_service_spec

    orig_dict = dynamic_sidecar_spec.model_dump(by_alias=True, exclude_unset=True)
    user_dict = user_aiodocker_service_spec.model_dump(
        by_alias=True, exclude_unset=True
    )

    another_merged_dict = nested_update(
        orig_dict,
        user_dict,
        include=_DYNAMIC_SIDECAR_SERVICE_EXTENDABLE_SPECS,
    )
    assert another_merged_dict


def test_regression__merge_service_base_and_user_specs():
    mock_service_spec = AioDockerServiceSpec.model_validate(
        {"Labels": {"l1": "false", "l0": "a"}}
    )
    mock_catalog_constraints = AioDockerServiceSpec.model_validate(
        {
            "Labels": {"l1": "true", "l2": "a"},
            "TaskTemplate": {
                "Placement": {
                    "Constraints": [
                        "c1==true",
                        "c2==true",
                    ],
                },
                "Resources": {
                    "Limits": {"MemoryBytes": 1, "NanoCPUs": 1},
                    "Reservations": {
                        "GenericResources": [
                            {"DiscreteResourceSpec": {"Kind": "VRAM", "Value": 1}}
                        ],
                        "MemoryBytes": 2,
                        "NanoCPUs": 2,
                    },
                },
                "ContainerSpec": {
                    "Env": [
                        "key-1=value-1",
                        "key2-value2=a",
                    ]
                },
            },
        }
    )
    result = _merge_service_base_and_user_specs(
        mock_service_spec, mock_catalog_constraints
    )
    assert result.model_dump(by_alias=True, exclude_unset=True) == {
        "Labels": {"l1": "true", "l2": "a", "l0": "a"},
        "TaskTemplate": {
            "Placement": {
                "Constraints": [
                    "c1==true",
                    "c2==true",
                ],
            },
            "Resources": {
                "Limits": {"MemoryBytes": 1, "NanoCPUs": 1},
                "Reservations": {
                    "GenericResources": [
                        {"DiscreteResourceSpec": {"Kind": "VRAM", "Value": 1}}
                    ],
                    "MemoryBytes": 2,
                    "NanoCPUs": 2,
                },
            },
            "ContainerSpec": {"Env": {"key-1": "value-1", "key2-value2": "a"}},
        },
    }
