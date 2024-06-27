# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import urllib.parse

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_catalog.services import ServiceUpdate
from models_library.api_schemas_webserver.catalog import DEVServiceGet
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import parse_obj_as
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        envs={
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",
        },
    )


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_dev_list_latest_services(
    client: TestClient,
    logged_user: UserInfoDict,
):
    assert client.app
    assert client.app.router

    # LIST latest
    url = client.app.router["dev_list_services_latest"].url_for()
    assert url.path.endswith("/catalog/services/-/latest")

    response = await client.get(f"{url}", params={"offset": "0", "limit": "1"})
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data
    assert error is None
    model = parse_obj_as(list[DEVServiceGet], data)
    assert model
    assert len(model) == 1


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_dev_get_and_patch_service(
    client: TestClient,
    logged_user: UserInfoDict,
):

    assert client.app
    assert client.app.router

    service_key = "simcore/services/dynamic/someservice"
    service_version = "3.4.5"

    url = client.app.router["dev_get_service"].url_for(
        service_key=urllib.parse.quote(service_key, safe=""),
        service_version=service_version,
    )

    # GET
    response = await client.get(
        f"{url}",
    )
    data, error = await assert_status(response, status.HTTP_200_OK)

    assert data
    assert error is None
    model = parse_obj_as(DEVServiceGet, data)
    assert model.key == service_key
    assert model.version == service_version

    # PATCH
    update = ServiceUpdate(name="foo", thumbnail=None, description="bar")
    response = await client.patch(
        f"{url}", json=jsonable_encoder(update, exclude_unset=True)
    )

    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data
    assert error is None
    model = parse_obj_as(DEVServiceGet, data)
    assert model.key == service_key
    assert model.version == service_version
    assert model.name == "foo"
    assert model.description == "bar"
