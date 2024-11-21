# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import urllib.parse
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.api_schemas_catalog.services import ServiceGetV2
from models_library.api_schemas_webserver.catalog import (
    CatalogServiceGet,
    CatalogServiceUpdate,
)
from models_library.products import ProductName
from models_library.rest_pagination import Page
from models_library.rpc_pagination import PageLimitInt, PageRpc
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import NonNegativeInt, TypeAdapter
from pytest_mock import MockerFixture
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


@pytest.fixture
def mocked_rpc_catalog_service_api(mocker: MockerFixture) -> dict[str, MagicMock]:
    async def _list(
        app: web.Application,
        *,
        product_name: ProductName,
        user_id: UserID,
        limit: PageLimitInt,
        offset: NonNegativeInt,
    ):
        assert app
        assert product_name
        assert user_id

        items = TypeAdapter(list[ServiceGetV2]).validate_python(
            ServiceGetV2.model_config["json_schema_extra"]["examples"],
        )
        total_count = len(items)

        return PageRpc[ServiceGetV2].create(
            items[offset : offset + limit],
            total=total_count,
            limit=limit,
            offset=offset,
        )

    async def _get(
        app: web.Application,
        *,
        product_name: ProductName,
        user_id: UserID,
        service_key: ServiceKey,
        service_version: ServiceVersion,
    ):
        assert app
        assert product_name
        assert user_id

        got = ServiceGetV2.model_validate(
            ServiceGetV2.model_config["json_schema_extra"]["examples"][0]
        )
        got.version = service_version
        got.key = service_key

        return got

    async def _update(
        app: web.Application,
        *,
        product_name: ProductName,
        user_id: UserID,
        service_key: ServiceKey,
        service_version: ServiceVersion,
        update: CatalogServiceUpdate,
    ):
        assert app
        assert product_name
        assert user_id

        got = ServiceGetV2.model_validate(
            ServiceGetV2.model_config["json_schema_extra"]["examples"][0]
        )
        got.version = service_version
        got.key = service_key
        return got.model_copy(update=update.model_dump(exclude_unset=True))

    return {
        "list_services_paginated": mocker.patch(
            "simcore_service_webserver.catalog._api.catalog_rpc.list_services_paginated",
            autospec=True,
            side_effect=_list,
        ),
        "get_service": mocker.patch(
            "simcore_service_webserver.catalog._api.catalog_rpc.get_service",
            autospec=True,
            side_effect=_get,
        ),
        "update_service": mocker.patch(
            "simcore_service_webserver.catalog._api.catalog_rpc.update_service",
            autospec=True,
            side_effect=_update,
        ),
    }


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_services_latest(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_rpc_catalog_service_api: dict[str, MagicMock],
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

    assert mocked_rpc_catalog_service_api["list_services_paginated"].call_count == 1


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_and_patch_service(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_rpc_catalog_service_api: dict[str, MagicMock],
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

    assert mocked_rpc_catalog_service_api["get_service"].call_count == 1
    assert not mocked_rpc_catalog_service_api["update_service"].called

    # PATCH
    update = CatalogServiceUpdate(
        name="foo",
        thumbnail=None,
        description="bar",
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
    assert model.description == update.description
    assert model.description_ui == update.description_ui
    assert model.version_display == update.version_display
    assert model.access_rights == update.access_rights

    assert mocked_rpc_catalog_service_api["get_service"].call_count == 1
    assert mocked_rpc_catalog_service_api["update_service"].call_count == 1


@pytest.mark.xfail(reason="service tags entrypoints under development")
@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_tags_in_services(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_rpc_catalog_service_api: dict[str, MagicMock],
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
