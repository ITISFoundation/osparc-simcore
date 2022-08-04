# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

from typing import Iterable
from unittest.mock import MagicMock

import pytest
from aiohttp.web import Application, HTTPNoContent
from faker import Faker
from pytest_mock.plugin import MockerFixture
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver import director_v2_core_dynamic_services
from simcore_service_webserver.application_settings import setup_settings
from yarl import URL

# FIXTURES


@pytest.fixture
def app(mock_env_devel_environment: dict[str, str]) -> Application:
    app = create_safe_application()
    setup_settings(app)
    return app


@pytest.fixture
def mocked_director_v2_request(mocker: MockerFixture) -> Iterable[MagicMock]:
    yield mocker.patch.object(director_v2_core_dynamic_services, "request_director_v2")


@pytest.fixture
def node_uuid(faker: Faker) -> str:
    return faker.uuid4()


# TESTS


@pytest.mark.parametrize("can_save", [True, False])
async def test_stop_dynamic_service_signature(
    app: Application,
    node_uuid: str,
    mocked_director_v2_request: MagicMock,
    can_save: bool,
):
    await director_v2_core_dynamic_services.stop_dynamic_service(
        app, node_uuid, save_state=can_save
    )
    mocked_director_v2_request.assert_called_with(
        app,
        "DELETE",
        url=URL(
            f"http://director-v2:8000/v2/dynamic_services/{node_uuid}?can_save={f'{can_save}'.lower()}"
        ),
        expected_status=HTTPNoContent,
        timeout=3610,
    )
