# pylint:disable=unused-argument
import re

import pytest
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses as AioResponsesMock
from common_library.users_enums import UserRole
from models_library.api_schemas_catalog.service_access_rights import (
    ServiceAccessRightsGet,
)
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.catalog._controller_rest_exceptions import (
    DefaultPricingUnitForServiceNotFoundError,
)
from simcore_service_webserver.catalog.catalog_service import (
    get_service_access_rights,
    is_catalog_service_responsive,
    list_user_services_with_versions,
)


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
@pytest.mark.parametrize(
    "backend_status_code", [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
)
async def test_server_responsive(
    client: TestClient,
    logged_user: UserInfoDict,
    aioresponses_mocker: AioResponsesMock,
    backend_status_code: int,
):
    aioresponses_mocker.get("http://catalog:8000", status=backend_status_code)

    assert client.app
    is_responsive = await is_catalog_service_responsive(app=client.app)
    if backend_status_code == status.HTTP_200_OK:
        assert is_responsive == True
    else:
        assert is_responsive == False


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
    await list_user_services_with_versions(
        app=client.app,
        user_id=logged_user["id"],
        product_name="osparc",
    )


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_service_access_rights(
    client: TestClient,
    logged_user: UserInfoDict,
    aioresponses_mocker: AioResponsesMock,
):
    url_pattern = re.compile(r"http://catalog:8000/.*")
    example = ServiceAccessRightsGet(
        service_key="simcore/services/comp/itis/sleeper",
        service_version="2.1.4",
        gids_with_access_rights={
            1: {"execute_access": True},
            5: {"execute_access": True},
        },
    )
    aioresponses_mocker.get(
        url_pattern,
        status=status.HTTP_200_OK,
        payload=example.model_dump(),
    )
    assert client.app
    access_rights = await get_service_access_rights(
        app=client.app,
        user_id=logged_user["id"],
        service_key="simcore/services/comp/itis/sleeper",
        service_version="2.1.4",
        product_name="osparc",
    )
    assert isinstance(access_rights, ServiceAccessRightsGet)


async def test_catalog_exceptions():

    error = DefaultPricingUnitForServiceNotFoundError(
        service_key="key", service_version="version"
    )
    assert isinstance(error.debug_message(), str)
