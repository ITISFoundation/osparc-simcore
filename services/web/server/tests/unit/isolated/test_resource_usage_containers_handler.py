# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

import asyncio

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.users import UserID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp.application import create_safe_application
from servicelib.aiohttp.typing_extension import Handler
from simcore_service_webserver._constants import RQ_PRODUCT_KEY
from simcore_service_webserver.resource_usage._containers_handlers import routes

_USER_ID = 1
_PRODUCT_NAME = "osparc"


@web.middleware
async def fake_discover_product_middleware(request: web.Request, handler: Handler):
    request[RQ_PRODUCT_KEY] = _PRODUCT_NAME
    response = await handler(request)
    return response


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client,
) -> TestClient:
    app = create_safe_application()
    app.middlewares.append(fake_discover_product_middleware)

    app.add_routes(routes)

    cli = event_loop.run_until_complete(aiohttp_client(app))
    return cli


@pytest.fixture
def mock_user_logged_in(mocker: MockerFixture) -> UserID:
    user_id = _USER_ID
    # patches @login_required decorator
    # NOTE: that these tests have no database!
    mocker.patch(
        "simcore_service_webserver.login.decorators.check_authorized",
        spec=True,
        return_value=user_id,
    )
    return user_id


@pytest.fixture
def mock_permission(mocker: MockerFixture):
    # patches @check_permission decorator
    mocker.patch(
        "simcore_service_webserver.security.decorators.check_permission",
        spec=True,
    )


@pytest.fixture
def mock_get_resource_usage_tracker_client(mocker: MockerFixture):
    return mocker.patch(
        "simcore_service_webserver.resource_usage._containers_api.resource_tracker_client.list_containers_by_user_and_product",
        autospec=True,
        return_value={
            "items": [
                {
                    "project_uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "project_name": "My Project 1",
                    "node_uuid": "e82e131b-d7c5-494e-86cb-c80255dd10bb",
                    "node_label": "My service/node custom name 1",
                    "service_key": "string",
                    "service_version": "string",
                    "start_time": "2023-07-02T08:52:16.486Z",
                    "duration": 23.3,
                    "processors": 0.5,
                    "core_hours": 40.775,
                    "status": "running",
                },
                {
                    "project_uuid": "ab1e0c06-b011-4b7d-8508-194018477385",
                    "project_name": "My Project 2",
                    "node_uuid": "cf6e634c-7133-4e58-ac1c-05484337836b",
                    "node_label": "My service/node custom name 2",
                    "service_key": "string",
                    "service_version": "string",
                    "start_time": "2023-07-02T08:52:16.486Z",
                    "duration": 7.7,
                    "processors": 2.0,
                    "core_hours": 53.9,
                    "status": "finished",
                },
            ],
            "total": 5,
            "offset": 0,
            "limit": 2,
            "links": {},
        },
    )


async def test_resource_usage_containers_handler(
    client: TestClient,
    mock_user_logged_in,
    mock_permission,
    mock_get_resource_usage_tracker_client,
):
    assert client.app
    url = client.app.router["list_resource_usage_containers"].url_for()

    # Call with default pagination
    resp = await client.get(f"{url}")
    data, _, meta, links = await assert_status(
        resp,
        web.HTTPOk,
        include_meta=True,
        include_links=True,
    )
    assert len(data) == 2
    assert meta["total"] == 5
    assert meta["offset"] == 0
    assert meta["limit"] == 20
    assert links
    mock_get_resource_usage_tracker_client.assert_called_once_with(
        app=client.app,
        user_id=_USER_ID,
        product_name=_PRODUCT_NAME,
        offset=0,
        limit=20,
    )

    # Call with custom pagination
    resp = await client.get(f'{url.with_query({"offset": 1, "limit": 2})}')
    data, _, meta, links = await assert_status(
        resp,
        web.HTTPOk,
        include_meta=True,
        include_links=True,
    )
    assert len(data) == 2
    assert meta["total"] == 5
    assert meta["offset"] == 1
    assert meta["limit"] == 2
    assert links
