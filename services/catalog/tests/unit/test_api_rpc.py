# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from fastapi import FastAPI
from models_library.products import ProductName
from models_library.rest_pagination import MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
from models_library.users import UserID
from pydantic import ValidationError
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
    monkeypatch.delenv("CATALOG_RABBITMQ", raising=False)
    return setenvs_from_dict(
        monkeypatch,
        {**app_environment, **rabbit_env_vars_dict},
    )


async def test_rcp_catalog_client(
    postgres_setup_disabled: None,
    director_setup_disabled: None,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
):
    assert app

    page = await list_services_paginated(
        rpc_client, product_name=product_name, user_id=user_id
    )

    assert page.data
    service_key = page.data[0].key
    service_version = page.data[0].version

    with pytest.raises(ValidationError):
        await list_services_paginated(
            rpc_client,
            product_name=product_name,
            user_id=user_id,
            limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE + 1,
        )

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
