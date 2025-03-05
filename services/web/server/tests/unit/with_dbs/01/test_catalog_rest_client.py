import re

import pytest
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses as AioResponsesMock
from common_library.users_enums import UserRole
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.catalog.catalog_service import (
    get_services_for_user_in_product,
    is_catalog_service_responsive,
)


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_server_responsive(
    client: TestClient, logged_user: UserInfoDict, aioresponses_mocker: AioResponsesMock
):
    aioresponses_mocker.get(
        "http://catalog:8000",
        status=status.HTTP_200_OK,
    )

    assert client.app
    assert await is_catalog_service_responsive(app=client.app) == True


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
@pytest.mark.parametrize(
    "backend_status_code", [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
)
async def test_get_services_for_user_in_product(
    client: TestClient,
    logged_user: UserInfoDict,
    aioresponses_mocker: AioResponsesMock,
    backend_status_code: int,
):
    url_pattern = re.compile(r"http://catalog:8000/.*")
    aioresponses_mocker.get(
        url_pattern,
        status=backend_status_code,
    )
    assert client.app
    _ = await get_services_for_user_in_product(
        app=client.app,
        user_id=logged_user["id"],
        product_name="osparc",
        only_key_versions=False,
    )
