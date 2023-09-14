# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable
from typing import Any, TypeAlias

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.wallets import WalletGet
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_service_webserver.db.models import UserRole

OpenApiDict: TypeAlias = dict[str, Any]


@pytest.fixture
def user_role():
    return UserRole.USER


@pytest.fixture
def create_new_wallet(client: TestClient, faker: Faker) -> Callable:
    assert client.app
    url = client.app.router["create_wallet"].url_for()

    async def _create():
        resp = await client.post(
            url.path,
            json={
                "name": f"wallet {faker.word()}",
                "description": "Fake wallet from create_new_wallet",
            },
        )
        data, _ = await assert_status(resp, web.HTTPCreated)
        return WalletGet.parse_obj(data)

    return _create


@pytest.fixture
async def logged_user_wallet(
    client: TestClient,
    logged_user: UserInfoDict,
    wallets_clean_db: None,
    create_new_wallet: Callable,
) -> WalletGet:
    assert client.app
    return await create_new_wallet()
