from collections.abc import AsyncIterator

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from models_library.license_goods import (
    LicenseGoodDB,
    LicenseGoodUpdateDB,
    LicenseResourceType,
)
from models_library.rest_ordering import OrderBy
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.resource_tracker_pricing_plans import (
    resource_tracker_pricing_plans,
)
from simcore_postgres_database.utils_repos import transaction_context
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.licenses import _license_goods_db
from simcore_service_webserver.licenses.errors import LicenseGoodNotFoundError
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
async def pricing_plan_id(
    client: TestClient,
    osparc_product_name: str,
) -> AsyncIterator[int]:
    assert client.app

    async with transaction_context(get_asyncpg_engine(client.app)) as conn:
        result = await conn.execute(
            resource_tracker_pricing_plans.insert()
            .values(
                product_name=osparc_product_name,
                display_name="ISolve Thermal",
                description="",
                classification="TIER",
                is_active=True,
                pricing_plan_key="isolve-thermal",
            )
            .returning(resource_tracker_pricing_plans.c.pricing_plan_id)
        )
        row = result.first()

    assert row

    yield int(row[0])

    async with transaction_context(get_asyncpg_engine(client.app)) as conn:
        result = await conn.execute(resource_tracker_pricing_plans.delete())


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_license_goods_db_crud(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: str,
    expected: HTTPStatus,
    pricing_plan_id: int,
):
    assert client.app

    output: tuple[int, list[LicenseGoodDB]] = await _license_goods_db.list_(
        client.app,
        product_name=osparc_product_name,
        offset=0,
        limit=10,
        order_by=OrderBy(field="modified"),
    )
    assert output[0] == 0

    license_good_db = await _license_goods_db.create(
        client.app,
        product_name=osparc_product_name,
        name="Model A",
        license_resource_type=LicenseResourceType.VIP_MODEL,
        pricing_plan_id=pricing_plan_id,
    )
    _license_good_id = license_good_db.license_good_id

    output: tuple[int, list[LicenseGoodDB]] = await _license_goods_db.list_(
        client.app,
        product_name=osparc_product_name,
        offset=0,
        limit=10,
        order_by=OrderBy(field="modified"),
    )
    assert output[0] == 1

    license_good_db = await _license_goods_db.get(
        client.app,
        license_good_id=_license_good_id,
        product_name=osparc_product_name,
    )
    assert license_good_db.name == "Model A"

    await _license_goods_db.update(
        client.app,
        license_good_id=_license_good_id,
        product_name=osparc_product_name,
        updates=LicenseGoodUpdateDB(name="Model B"),
    )

    license_good_db = await _license_goods_db.get(
        client.app,
        license_good_id=_license_good_id,
        product_name=osparc_product_name,
    )
    assert license_good_db.name == "Model B"

    license_good_db = await _license_goods_db.delete(
        client.app,
        license_good_id=_license_good_id,
        product_name=osparc_product_name,
    )

    with pytest.raises(LicenseGoodNotFoundError):
        await _license_goods_db.get(
            client.app,
            license_good_id=_license_good_id,
            product_name=osparc_product_name,
        )
