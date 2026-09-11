# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from collections.abc import AsyncIterator
from typing import Any

import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.products import ProductName
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from servicelib.aiohttp.observer import register_observer
from simcore_postgres_database.models.groups import groups, user_to_groups
from simcore_postgres_database.models.products import products
from simcore_service_webserver.constants import FRONTEND_APP_DEFAULT
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.users import users_product_access_service
from sqlalchemy.ext.asyncio import AsyncEngine

_SIGNAL_ON_USER_CONFIRMATION: str = "SIGNAL_ON_USER_CONFIRMATION"


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_DB_LISTENER": "0",
            # the wallets plugin subscribes to SIGNAL_ON_USER_CONFIRMATION
            # (default wallet creation): keep it out of this seam test so the
            # probe observer registered below is the only subscriber
            "WEBSERVER_WALLETS": "0",
        },
    )


@pytest.fixture
async def user(client: TestClient, user_email: str) -> AsyncIterator[UserInfoDict]:
    # NOTE: overrides the default `user` fixture to control the email, so that
    # it can be matched by the inclusion rules below
    assert client.app
    async with NewUser({"email": user_email}, app=client.app) as user_info:
        yield user_info


@pytest.fixture
async def inclusion_rule_group(asyncpg_engine: AsyncEngine, user_email: str) -> AsyncIterator[dict[str, Any]]:
    """A STANDARD group whose inclusion_rules match this test's user email"""
    # pylint: disable=contextmanager-generator-missing-cleanup
    async with insert_and_get_row_lifespan(
        asyncpg_engine,
        table=groups,
        values={
            "name": "Grant Product Access Test Group",
            "description": "auto-membership via inclusion rules",
            "type": "STANDARD",
            "inclusion_rules": {"email": re.escape(user_email)},
        },
        pk_col=groups.c.gid,
    ) as group_row:
        yield group_row


@pytest.fixture
def second_product_name(app_products_names: list[ProductName]) -> ProductName:
    # every NewUser is already granted the default product, so use another one
    # (seeded, with its product group, by `app_products_names`)
    return next(n for n in app_products_names if n != FRONTEND_APP_DEFAULT)


@pytest.fixture
def signal_calls(client: TestClient) -> list[dict[str, Any]]:
    """Probe observer on SIGNAL_ON_USER_CONFIRMATION recording its calls"""
    assert client.app
    calls: list[dict[str, Any]] = []

    async def _probe(**kwargs: Any) -> None:
        calls.append(kwargs)

    register_observer(client.app, _probe, _SIGNAL_ON_USER_CONFIRMATION)
    return calls


async def _fetch_user_group_ids(app: web.Application, user_id: int) -> set[int]:
    async with get_asyncpg_engine(app).begin() as conn:
        result = await conn.execute(sa.select(user_to_groups.c.gid).where(user_to_groups.c.uid == user_id))
        return {row.gid for row in result}


async def _fetch_product_group_id(app: web.Application, product_name: ProductName) -> int:
    async with get_asyncpg_engine(app).connect() as conn:
        result = await conn.execute(sa.select(products.c.group_id).where(products.c.name == product_name))
        group_id = result.scalar_one_or_none()
    assert group_id is not None, f"no group associated to product {product_name}"
    return int(group_id)


async def test_grant_user_access_to_product_adds_groups_and_emits_signal(
    client: TestClient,
    user: UserInfoDict,
    inclusion_rule_group: dict[str, Any],
    second_product_name: ProductName,
    signal_calls: list[dict[str, Any]],
):
    assert client.app

    product_group_id = await _fetch_product_group_id(client.app, second_product_name)

    # pre-condition: not member of the inclusion-rule group nor of the product group
    gids_before = await _fetch_user_group_ids(client.app, user["id"])
    assert inclusion_rule_group["gid"] not in gids_before
    assert product_group_id not in gids_before

    await users_product_access_service.grant_user_access_to_product(
        client.app,
        user_id=user["id"],
        product_name=second_product_name,
        extra_credits_in_usd=10,
    )

    # 1. membership in the inclusion-rule group (auto_add_user_to_groups)
    gids_after = await _fetch_user_group_ids(client.app, user["id"])
    assert inclusion_rule_group["gid"] in gids_after

    # 2. membership in the product group (auto_add_user_to_product_group)
    assert product_group_id in gids_after

    # 3. SIGNAL_ON_USER_CONFIRMATION emitted exactly once with the right kwargs
    assert signal_calls == [
        {
            "user_id": user["id"],
            "product_name": second_product_name,
            "extra_credits_in_usd": 10,
        }
    ]


async def test_grant_user_access_to_product_is_idempotent(
    client: TestClient,
    user: UserInfoDict,
    inclusion_rule_group: dict[str, Any],
    second_product_name: ProductName,
    signal_calls: list[dict[str, Any]],
):
    assert client.app

    for _ in range(2):
        await users_product_access_service.grant_user_access_to_product(
            client.app,
            user_id=user["id"],
            product_name=second_product_name,
            extra_credits_in_usd=None,
        )

    # no duplicated memberships (one row per group)
    async with get_asyncpg_engine(client.app).connect() as conn:
        result = await conn.execute(
            sa.select(sa.func.count()).select_from(user_to_groups).where(user_to_groups.c.uid == user["id"])
        )
        total = int(result.scalar())
    gids_after = await _fetch_user_group_ids(client.app, user["id"])
    assert total == len(gids_after)
    assert inclusion_rule_group["gid"] in gids_after

    # the signal is still emitted on every call (observers are idempotent)
    assert len(signal_calls) == 2
    assert all(call["extra_credits_in_usd"] is None for call in signal_calls)
