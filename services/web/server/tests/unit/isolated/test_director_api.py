# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module


import json
import re
from typing import Dict

import pytest
from aiohttp.client import ClientSession
from aiohttp.web_routedef import static
from aioresponses.core import CallbackResult, aioresponses
from faker import Faker
from models_library.services import ServiceDockerData
from servicelib.client_session import get_client_session
from simcore_service_webserver.director.config import (
    APP_DIRECTOR_API_KEY,
    DirectorSettings,
)
from simcore_service_webserver.director.director_api import (
    get_running_interactive_services,
    get_service_by_key_version,
    get_services_extras,
    start_service,
    stop_service,
    stop_services,
)


@pytest.fixture
async def director_service_api_mock(loop, faker: Faker) -> aioresponses:
    #
    # Mocks director's service API api/specs/director/openapi.yaml
    #
    #

    # GET /running_interactive_services
    class get_running_interactive_services:
        pattern = re.compile(
            r"^http://[a-z\-_]*director:[0-9]+/v0/running_interactive_services$"
        )

        @staticmethod
        def handler(url, **kwargs):
            def _create(n):
                return dict(
                    published_port=faker.unique.random_int(),
                    entry_point="/the/entry/point/is/here",
                    service_uuid=faker.unique.uuid4(cast_to=str),
                    service_key=f"simcore/services/comp/itis/{faker.unique.word()}",
                    service_version=".".join(str(faker.random_int()) for _ in range(3)),
                    service_host="jupyter_E1O2E-LAH",
                    service_port=faker.unique.random_int(80, 10000),
                    service_basepath="/x/E1O2E-LAH",
                    service_state=faker.random_choices(["pending", "starting"]),
                    service_message=faker.unique.sentence(),
                )

            return CallbackResult(payload={"data": [_create(n) for n in range(3)]})

    # POST /running_interactive_services
    start_service = re.compile(
        r"^http://[a-z\-_]*director:[0-9]+/v0/running_interactive_services$"
    )

    # DELETE /running_interactive_services/{service_uuid}
    stop_service = re.compile(
        r"^http://[a-z\-_]*director:[0-9]+/v0/running_interactive_services/.+$"
    )

    # GET /service_extras/{service_key}/{service_version}
    get_service_by_key_version = re.compile(
        r"^http://[a-z\-_]*director:[0-9]+/v0/services/\w+/.+$"
    )

    # GET /services/{service_key}/{service_version}
    get_service_extras = re.compile(
        r"^http://[a-z\-_]*director:[0-9]+/v0/service_extras/\w+/.+$"
    )

    with aioresponses() as mock:
        mock.get(
            get_running_interactive_services.pattern,
            status=200,
            callback=get_running_interactive_services.handler,
        )
        mock.post(start_service, status=200, payload={"data": {}})
        mock.delete(
            stop_service,
            status=204,
        )

        mock.get(get_service_by_key_version, status=200, payload={"data": {}})
        mock.get(get_service_extras, status=200, payload={"data": {}})

        yield mock


@pytest.mark.skip(reason="dev")
async def test_mocks(director_service_api_mock):
    async with ClientSession() as session:
        async with session.get(
            "http://director:8000/v0/running_interactive_services"
        ) as resp:
            assert resp.status == 200
            print(await resp.json())


@pytest.fixture
def app_mock(director_service_api_mock):
    # we only need the app as a container of the aiohttp client session and
    # the director entrypoint
    #
    settings = DirectorSettings()

    app = {}
    app[APP_DIRECTOR_API_KEY] = str(settings.url)
    single_client_in_app = get_client_session(app)
    assert single_client_in_app
    assert single_client_in_app is get_client_session(app)

    return app


async def test_director_api_client_calls(app):

    # check services running in my study
    services = await get_running_interactive_services(
        app, user_id="1", project_id="dc7d6847-a3b7-4905-bbfb-777e3bd433c8"
    )

    service = await get_service_by_key_version(
        app, service_key="simcore/comp/isolve", service_version="1.0.3"
    )

    extras = await get_services_extras(
        app, service_key="simcore/comp/isolve", service_version="1.0.3"
    )

    started = await start_service(
        app,
        user_id="1",
        project_id="dc7d6847-a3b7-4905-bbfb-777e3bd433c8",
        service_key="simcore/comp/isolve",
        service_version="1.0.3",
        service_uuid="43946ec4-fb14-4667-a81b-df6e8375282d",
    )

    await stop_service(app, started["uuid"])

    await stop_services(app, project_id="dc7d6847-a3b7-4905-bbfb-777e3bd433c8")
