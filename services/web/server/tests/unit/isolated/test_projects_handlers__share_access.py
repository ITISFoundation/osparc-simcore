# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

import asyncio

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.services import ServiceKeyVersion
from models_library.users import UserID
from pytest_mock import MockerFixture
from servicelib.aiohttp.application import create_safe_application
from servicelib.aiohttp.typing_extension import Handler
from simcore_service_webserver._constants import RQ_PRODUCT_KEY
from simcore_service_webserver.projects.projects_handlers import routes


@web.middleware
async def fake_discover_product_middleware(request: web.Request, handler: Handler):
    request[RQ_PRODUCT_KEY] = "osparc"
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
    user_id = 1
    # patches @login_required decorator
    # NOTE: that these tests have no database!
    mocker.patch(
        "simcore_service_webserver.login.decorators.check_authorized",
        spec=True,
        return_value=user_id,
    )
    return user_id


@pytest.fixture
def mock_perimission(mocker: MockerFixture):
    # patches @check_permission decorator
    mocker.patch(
        "simcore_service_webserver.security.decorators.check_permission",
        spec=True,
    )


@pytest.fixture
def mock_projects_api_get_project_for_user(mocker: MockerFixture):
    return mocker.patch(
        "simcore_service_webserver.projects.projects_handlers.projects_api.get_project_for_user",
        spec=True,
        return_value={
            "workbench": {
                "fc9208d9-1a0a-430c-9951-9feaf1de3368": {
                    "key": "simcore/services/frontend/data-iterator/int-range",
                    "version": "1.0.0",
                    "label": "Integer iterator",
                    "inputs": {
                        "linspace_start": 0,
                        "linspace_stop": 3,
                        "linspace_step": 1,
                    },
                    "inputNodes": [],
                    "parent": None,
                    "thumbnail": "",
                },
                "87663253-cecb-40e8-8429-dd2cd875166e": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "2.0.2",
                    "label": "sleeper",
                    "inputs": {
                        "input_2": {
                            "nodeUuid": "fc9208d9-1a0a-430c-9951-9feaf1de3368",
                            "output": "out_1",
                        },
                        "input_3": False,
                    },
                    "inputNodes": ["fc9208d9-1a0a-430c-9951-9feaf1de3368"],
                    "parent": None,
                    "thumbnail": "",
                    "state": {
                        "modified": True,
                        "dependencies": [],
                        "currentStatus": "NOT_STARTED",
                    },
                },
                "305e9552-06fd-48a5-b9bc-36a8563fed67": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "2.0.3",
                    "label": "sleeper_2",
                    "inputs": {
                        "input_1": {
                            "nodeUuid": "87663253-cecb-40e8-8429-dd2cd875166e",
                            "output": "output_1",
                        },
                        "input_2": {
                            "nodeUuid": "87663253-cecb-40e8-8429-dd2cd875166e",
                            "output": "output_2",
                        },
                        "input_3": False,
                    },
                    "inputNodes": ["87663253-cecb-40e8-8429-dd2cd875166e"],
                    "parent": None,
                    "thumbnail": "",
                    "state": {
                        "modified": True,
                        "dependencies": ["87663253-cecb-40e8-8429-dd2cd875166e"],
                        "currentStatus": "NOT_STARTED",
                    },
                },
            },
        },
    )


@pytest.fixture
def mock_catalog_client_list_inaccessible_services(mocker: MockerFixture):
    return mocker.patch(
        "simcore_service_webserver.projects.projects_handlers.catalog_client.list_inaccessible_services",
        spec=True,
        return_value=[],
    )


async def test_denied_share_access_project_handler(
    client: TestClient,
    mock_user_logged_in,
    mock_perimission,
    mock_projects_api_get_project_for_user,
    mock_catalog_client_list_inaccessible_services,
):
    GID = 5
    PROJECT_UUID = "da5068e0-8a8d-4fb9-9516-56e5ddaef15b"
    PRODUCT_NAME = "osparc"

    assert client.app
    url = client.app.router["denied_share_access_project"].url_for(
        project_id=PROJECT_UUID
    )
    resp = await client.get(f"{url}?with_gid={GID}")
    resp_json = await resp.json()

    assert resp.status == 200
    assert resp_json == {"data": []}
    mock_projects_api_get_project_for_user.assert_called_once_with(
        client.app,
        project_uuid=PROJECT_UUID,
        user_id=mock_user_logged_in,
        include_state=True,
    )
    mock_catalog_client_list_inaccessible_services.assert_called_once_with(
        client.app,
        GID,
        PRODUCT_NAME,
        [
            ServiceKeyVersion(
                key="simcore/services/frontend/data-iterator/int-range", version="1.0.0"
            ),
            ServiceKeyVersion(
                key="simcore/services/comp/itis/sleeper", version="2.0.2"
            ),
            ServiceKeyVersion(
                key="simcore/services/comp/itis/sleeper", version="2.0.3"
            ),
        ],
    )
