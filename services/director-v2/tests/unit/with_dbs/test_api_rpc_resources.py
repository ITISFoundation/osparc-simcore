# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import re
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from random import choice
from typing import Any

import pytest
import respx
from fastapi import FastAPI
from models_library.products import ProductName
from models_library.service_settings_labels import SimcoreServiceLabels
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.director_v2 import (
    resources as rpc_resources,
)
from settings_library.redis import RedisSettings
from simcore_postgres_database.models.groups_extra_properties import (
    groups_extra_properties,
)
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.modules.dynamic_sidecar.docker_service_specs.settings import (
    compute_helper_containers_resources,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def mock_env(
    monkeypatch: pytest.MonkeyPatch,
    mock_env: EnvVarsDict,
    fake_s3_envs: EnvVarsDict,
    postgres_host_config: dict[str, str],
    rabbit_env_vars_dict: EnvVarsDict,
    redis_service: RedisSettings,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **mock_env,
            **fake_s3_envs,
            **rabbit_env_vars_dict,
            "COMPUTATIONAL_BACKEND_ENABLED": "true",
            "COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED": "true",
            "POSTGRES_HOST": postgres_host_config["host"],
            "POSTGRES_USER": postgres_host_config["user"],
            "POSTGRES_PASSWORD": postgres_host_config["password"],
            "POSTGRES_DB": postgres_host_config["database"],
        },
    )


@pytest.fixture
def fake_service_labels_with_tracing() -> dict[str, Any]:
    # NOTE: tracing and egress-proxy count are both derived from the service labels.
    # NOTE: both fields are aliased (e.g. simcore.service.tracing) in the raw/wire
    # format, so the ALIASED keys must be overridden (not the python field names)
    # for the override to actually take effect once respx serves this dict as JSON.
    example: dict[str, Any] = choice(  # noqa: S311
        SimcoreServiceLabels.model_json_schema()["examples"]  # type: ignore
    )
    return {
        **example,
        "simcore.service.tracing": True,
        "simcore.service.containers-allowed-outgoing-permit-list": None,
    }


@pytest.fixture
def mock_catalog_service_get_service_labels(
    initialized_app: FastAPI,
    fake_service_labels_with_tracing: dict[str, Any],
) -> Iterator[respx.MockRouter]:
    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=f"{initialized_app.state.settings.DIRECTOR_V2_CATALOG.api_base_url}",
        assert_all_called=True,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.get(
            re.compile(r"/services/simcore%2Fservices%2F(comp|dynamic|frontend)%2F[^/]+/\d+\.\d+\.\d+/labels"),
            name="get_service_labels",
        ).respond(json=fake_service_labels_with_tracing)
        yield respx_mock


@pytest.fixture
async def enable_data_mounting(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[Callable[[int, ProductName], Awaitable[None]]]:
    inserted_group_ids: list[int] = []

    async def _(group_id: int, product_name: ProductName) -> None:
        async with sqlalchemy_async_engine.begin() as con:
            await con.execute(
                groups_extra_properties.insert().values(
                    group_id=group_id,
                    product_name=product_name,
                    mount_data=True,
                )
            )
        inserted_group_ids.append(group_id)

    yield _

    async with sqlalchemy_async_engine.begin() as con:
        await con.execute(
            groups_extra_properties.delete().where(groups_extra_properties.c.group_id.in_(inserted_group_ids))
        )


async def test_rpc_get_helper_containers_resources(
    initialized_app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    create_registered_user: Callable[..., dict[str, Any]],
    with_product: dict[str, Any],
    product_name: ProductName,
    enable_data_mounting: Callable[[int, ProductName], Awaitable[None]],
    mock_catalog_service_get_service_labels: respx.MockRouter,
):
    user = create_registered_user()
    await enable_data_mounting(user["primary_gid"], product_name)

    max_user_service_container_memory = TypeAdapter(ByteSize).validate_python("2GiB")

    cpu, ram = await rpc_resources.get_helper_containers_resources(
        rpc_client,
        user_id=user["id"],
        product_name=product_name,
        service_key="simcore/services/dynamic/sim4life",
        service_version="1.0.0",
        max_user_service_container_memory=max_user_service_container_memory,
    )

    assert mock_catalog_service_get_service_labels["get_service_labels"].called

    # NOTE: with_tracing=True (from the mocked labels) and with_rclone=True (from the DB
    # row inserted by enable_data_mounting) and egress_proxy_count=0 (no permit list set)
    app_settings: AppSettings = initialized_app.state.settings
    expected_cpu, expected_ram = compute_helper_containers_resources(
        dynamic_services_settings=app_settings.DYNAMIC_SERVICES,
        egress_proxy_count=0,
        with_tracing=True,
        with_rclone=True,
        max_user_service_container_memory=max_user_service_container_memory,
    )
    assert cpu == expected_cpu
    assert ram == expected_ram
    assert cpu > 0
    assert ram > 0
