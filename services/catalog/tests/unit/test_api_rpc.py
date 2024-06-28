# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from fastapi import FastAPI
from models_library.products import ProductName
from models_library.users import UserID
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.catalog.services import (
    get_service,
    list_services_paginated,
    update_service,
)

pytest_simcore_core_services_selection = [
    "rabbit",
]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    rabbit_env_vars_dict: EnvVarsDict,  # rabbitMQ settings from 'rabbit' service
) -> EnvVarsDict:
    for name in ("CATALOG_RABBITMQ", "CATALOG_DIRECTOR", "CATALOG_POSTGRES"):
        monkeypatch.delenv(name, raising=False)
        app_environment.pop(name, None)

    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **rabbit_env_vars_dict,
            "CATALOG_DIRECTOR": "null",  # disabled
            "CATALOG_POSTGRES": "null",  # disabled
        },
    )


async def test_rcp_catalog_client(
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
):
    assert app

    page = await list_services_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        limit=10,
        offset=0,
    )

    assert page.data
    service_key = page.data[0].key
    service_version = page.data[0].version

    got = await get_service(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )
    assert got.key == service_key
    assert got.version == service_version

    updated = await update_service(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        update={
            "name": "foo",
            "thumbnail": None,
            "description": "bar",
            "classifiers": None,
        },
    )

    assert updated.key == got.key
    assert updated.version == got.version
    assert updated.name == "foo"
