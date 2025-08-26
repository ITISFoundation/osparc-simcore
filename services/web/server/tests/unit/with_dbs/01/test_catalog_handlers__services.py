# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import re
import urllib.parse
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses as AioResponsesMock
from faker import Faker
from models_library.api_schemas_catalog.services import ServiceGetV2
from models_library.api_schemas_webserver.catalog import (
    CatalogServiceGet,
    CatalogServiceUpdate,
)
from models_library.rest_pagination import Page
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import TypeAdapter
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.catalog_rpc_server import CatalogRpcSideEffects
from pytest_simcore.helpers.faker_factories import random_icon_url
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.catalog._controller_rest_schemas import (
    ServiceInputGet,
    ServiceOutputGet,
)
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


@pytest.fixture
def mocked_catalog_rpc_api(mocker: MockerFixture) -> dict[str, MockType]:

    side_effects = CatalogRpcSideEffects()

    return {
        "list_services_paginated": mocker.patch(
            "simcore_service_webserver.catalog._service.catalog_rpc.list_services_paginated",
            autospec=True,
            side_effect=side_effects.list_services_paginated,
        ),
        "get_service": mocker.patch(
            "simcore_service_webserver.catalog._service.catalog_rpc.get_service",
            autospec=True,
            side_effect=side_effects.get_service,
        ),
        "update_service": mocker.patch(
            "simcore_service_webserver.catalog._service.catalog_rpc.update_service",
            autospec=True,
            side_effect=side_effects.update_service,
        ),
    }


@pytest.fixture
def mocked_catalog_rest_api(aioresponses_mocker: AioResponsesMock) -> dict[str, Any]:
    """Fixture that mocks catalog service responses for tests"""
    url_pattern = re.compile(r"http://catalog:8000/v0/services/.*")
    service_payload = ServiceGetV2.model_json_schema()["examples"][0]

    # Mock multiple responses as needed by tests
    for _ in range(6):  # Increased to accommodate all tests
        aioresponses_mocker.get(
            url_pattern,
            status=status.HTTP_200_OK,
            payload=service_payload,
        )

    service_key = "simcore/services/comp/itis/sleeper"
    service_version = "0.1.0"

    return {
        "service_key": service_key,
        "service_version": service_version,
        "service_payload": service_payload,
    }


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_services_latest(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_catalog_rpc_api: dict[str, MockType],
):
    assert client.app
    assert client.app.router

    url = client.app.router["list_services_latest"].url_for()
    assert url.path.endswith("/catalog/services/-/latest")

    response = await client.get(f"{url}", params={"offset": "0", "limit": "1"})
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data
    assert error is None

    model = Page[CatalogServiceGet].model_validate(data)
    assert model
    assert model.data
    assert len(model.data) == model.meta.count

    assert mocked_catalog_rpc_api["list_services_paginated"].call_count == 1


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_inputs(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_catalog_rest_api: dict[str, Any],
):
    assert client.app
    assert client.app.router

    service_key = mocked_catalog_rest_api["service_key"]
    service_version = mocked_catalog_rest_api["service_version"]

    url = client.app.router["list_service_inputs"].url_for(
        service_key=urllib.parse.quote(service_key, safe=""),
        service_version=service_version,
    )

    response = await client.get(f"{url}")
    data, _ = await assert_status(response, status.HTTP_200_OK)
    TypeAdapter(list[ServiceInputGet]).validate_python(data)


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_outputs(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_catalog_rest_api: dict[str, Any],
):
    assert client.app
    assert client.app.router

    service_key = mocked_catalog_rest_api["service_key"]
    service_version = mocked_catalog_rest_api["service_version"]

    url = client.app.router["list_service_outputs"].url_for(
        service_key=urllib.parse.quote(service_key, safe=""),
        service_version=service_version,
    )

    response = await client.get(f"{url}")
    data, _ = await assert_status(response, status.HTTP_200_OK)
    TypeAdapter(list[ServiceOutputGet]).validate_python(data)


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_outputs(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_catalog_rest_api: dict[str, Any],
):
    assert client.app
    assert client.app.router

    service_key = mocked_catalog_rest_api["service_key"]
    service_version = mocked_catalog_rest_api["service_version"]
    service_payload = mocked_catalog_rest_api["service_payload"]

    url = client.app.router["get_service_output"].url_for(
        service_key=urllib.parse.quote(service_key, safe=""),
        service_version=service_version,
        output_key=next(iter(service_payload["outputs"].keys())),
    )

    response = await client.get(f"{url}")
    data, _ = await assert_status(response, status.HTTP_200_OK)
    ServiceOutputGet.model_validate(data)


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_inputs(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_catalog_rest_api: dict[str, Any],
):
    assert client.app
    assert client.app.router

    service_key = mocked_catalog_rest_api["service_key"]
    service_version = mocked_catalog_rest_api["service_version"]
    service_payload = mocked_catalog_rest_api["service_payload"]

    url = client.app.router["get_service_input"].url_for(
        service_key=urllib.parse.quote(service_key, safe=""),
        service_version=service_version,
        input_key=next(iter(service_payload["inputs"].keys())),
    )
    response = await client.get(f"{url}")
    data, _ = await assert_status(response, status.HTTP_200_OK)
    ServiceInputGet.model_validate(data)


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_compatible_inputs_given_source_outputs(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_catalog_rest_api: dict[str, Any],
):
    assert client.app
    assert client.app.router

    service_key = mocked_catalog_rest_api["service_key"]
    service_version = mocked_catalog_rest_api["service_version"]

    # Get compatible inputs given source outputs
    url = (
        client.app.router["get_compatible_inputs_given_source_output"]
        .url_for(
            service_key=urllib.parse.quote(service_key, safe=""),
            service_version=service_version,
        )
        .with_query(
            {
                "fromService": service_key,
                "fromVersion": service_version,
                "fromOutput": "output_1",
            }
        )
    )
    response = await client.get(f"{url}")
    _, _ = await assert_status(response, status.HTTP_200_OK)


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_compatible_outputs_given_target_inputs(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_catalog_rest_api: dict[str, Any],
):
    assert client.app
    assert client.app.router

    service_key = mocked_catalog_rest_api["service_key"]
    service_version = mocked_catalog_rest_api["service_version"]

    url = (
        client.app.router["get_compatible_outputs_given_target_input"]
        .url_for(
            service_key=urllib.parse.quote(service_key, safe=""),
            service_version=service_version,
        )
        .with_query(
            {
                "toService": service_key,
                "toVersion": service_version,
                "toInput": "input_1",
            }
        )
    )
    response = await client.get(f"{url}")
    _, _ = await assert_status(response, status.HTTP_200_OK)


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_and_patch_service(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_catalog_rpc_api: dict[str, MockType],
    faker: Faker,
):
    assert client.app
    assert client.app.router

    service_key = "simcore/services/dynamic/someservice"
    service_version = "3.4.5"

    url = client.app.router["get_service"].url_for(
        service_key=urllib.parse.quote(service_key, safe=""),
        service_version=service_version,
    )

    # GET
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)

    assert data
    assert error is None
    model = CatalogServiceGet.model_validate(data)
    assert model.key == service_key
    assert model.version == service_version

    assert mocked_catalog_rpc_api["get_service"].call_count == 1
    assert not mocked_catalog_rpc_api["update_service"].called

    # PATCH
    update = CatalogServiceUpdate(
        name="foo",
        description="bar",
        icon=random_icon_url(faker),
        classifiers=None,
        versionDisplay="Some nice name",
        descriptionUi=True,
        accessRights={1: {"execute": True, "write": True}},
    )
    response = await client.patch(
        f"{url}", json=jsonable_encoder(update, exclude_unset=True)
    )

    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data
    assert error is None

    model = CatalogServiceGet.model_validate(data)
    assert model.key == service_key
    assert model.version == service_version
    assert model.name == update.name
    assert model.icon == update.icon
    assert model.description == update.description
    assert model.description_ui == update.description_ui
    assert model.version_display == update.version_display
    assert model.access_rights == update.access_rights

    assert mocked_catalog_rpc_api["get_service"].call_count == 1
    assert mocked_catalog_rpc_api["update_service"].call_count == 1


@pytest.mark.xfail(reason="service tags entrypoints under development")
@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_tags_in_services(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_catalog_rpc_api: dict[str, MockType],
):
    assert client.app
    assert client.app.router

    service_key = "simcore/services/dynamic/someservice"
    service_version = "3.4.5"

    # the service
    url = client.app.router["get_service"].url_for(
        service_key=urllib.parse.quote(service_key, safe=""),
        service_version=service_version,
    )
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert not error

    # list tags
    url = client.app.router["list_service_tags"].url_for(
        service_key=urllib.parse.quote(service_key, safe=""),
        service_version=service_version,
    )
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)

    assert not error
    assert not data

    # create a tag
    fake_tag = {"name": "tag1", "description": "description1", "color": "#f00"}
    url = client.app.router["create_tag"].url_for()
    resp = await client.post(f"{url}", json=fake_tag)
    tag, _ = await assert_status(resp, status.HTTP_201_CREATED)

    tag_id = tag["id"]
    assert tag["name"] == fake_tag["name"]

    # add_service_tag
    url = client.app.router["add_service_tag"].url_for(
        service_key=urllib.parse.quote(service_key, safe=""),
        service_version=service_version,
        tag_id=tag_id,
    )
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)

    # list_service_tags
    url = client.app.router["list_service_tags"].url_for(
        service_key=urllib.parse.quote(service_key, safe=""),
        service_version=service_version,
    )
    response = await client.put(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)

    assert not error
    assert len(data) == 1

    # remove_service_tag
    url = client.app.router["remove_service_tag"].url_for(
        service_key=urllib.parse.quote(service_key, safe=""),
        service_version=service_version,
        tag_id=tag_id,
    )
    response = await client.delete(f"{url}")
    data, error = await assert_status(response, status.HTTP_204_NO_CONTENT)

    # list_service_tags
    url = client.app.router["list_service_tags"].url_for(
        service_key=urllib.parse.quote(service_key, safe=""),
        service_version=service_version,
    )
    response = await client.put(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)

    assert not error
    assert not data
