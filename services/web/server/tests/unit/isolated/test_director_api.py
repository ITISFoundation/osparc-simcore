# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module
"""
    Tests services/web/server/src/simcore_service_webserver/director/director_api.py which ...
    - is a submodule part of the 'director' app module at the webserver
    - provides function interface that simplifies requests to the 'director service'
    - NOTE: was deprecated and  shall use instead 'director-v2' service

"""
import json
import re
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml
from aioresponses.core import CallbackResult, aioresponses
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.director.director_api import (
    get_running_interactive_services,
    get_service_by_key_version,
    start_service,
    stop_services,
)
from simcore_service_webserver.director.plugin import setup_director
from yarl import URL


@pytest.fixture(scope="session")
def director_openapi_dir(osparc_simcore_root_dir: Path) -> Path:
    base_dir = osparc_simcore_root_dir / "api" / "specs" / "director"
    assert base_dir.exists()
    return base_dir


@pytest.fixture(scope="session")
def director_openapi_specs(director_openapi_dir: Path) -> dict[str, Any]:
    openapi_path = director_openapi_dir / "openapi.yaml"
    openapi_specs = yaml.safe_load(openapi_path.read_text())
    return openapi_specs


@pytest.fixture(scope="session")
def running_service_model_schema(osparc_simcore_root_dir: Path) -> dict:
    # SEE: https://github.com/ITISFoundation/osparc-simcore/tree/master/api/specs/common/schemas/running_service.yaml#L30
    content = yaml.safe_load(
        (
            osparc_simcore_root_dir / "api/specs/common/schemas/running_service.yaml"
        ).read_text()
    )
    schema = content["components"]["schemas"]["RunningServiceType"]

    # Creates fake instances of RunningServiceType model
    # Check dump manually in https://json-schema-faker.js.org/
    print(json.dumps(schema))

    return schema


@pytest.fixture(scope="session")
def registry_service_model_schema(osparc_simcore_root_dir: Path) -> dict:
    # SEE: https://github.com/ITISFoundation/osparc-simcore/tree/master/api/specs/common/schemas/services.yaml#L11
    #      https://github.com/ITISFoundation/osparc-simcore/tree/master/api/specs/common/schemas/node-meta-v0.0.1.json
    schema = json.loads(
        (
            osparc_simcore_root_dir / "api/specs/common/schemas/node-meta-v0.0.1.json"
        ).read_text()
    )

    # Check dump manually in https://json-schema-faker.js.org/
    print(json.dumps(schema))

    return schema


@pytest.fixture(scope="session")
def model_fake_factory(random_json_from_schema: Callable) -> Callable:
    """
    Adapter to create fake data instances of a mo
    """

    def _create(schema: dict, **override_attrs):
        model_instance = random_json_from_schema(json.dumps(schema))
        model_instance.update(override_attrs)

        # TODO: validate model instance including overrides?

        return model_instance

    return _create


# SCENARIO / TEST CONTEXT -----------------
#
# For the sake of simplicity, the director service is
# mocked assuming a concrete context/scenario:
#


@pytest.fixture(scope="module")
def user_id():
    return 1


@pytest.fixture(scope="module")
def project_id():
    return "dc7d6847-a3b7-4905-bbfb-777e3bd433c8"


@pytest.fixture(scope="module")
def project_nodes():
    return [
        "simcore/services/dynamic/smash:1.0.3:4fc8d1e6-a06c-451a-8eb8-2f64b8f93efa".split(
            ":"
        ),
        "simcore/services/dynamic/jupyter:3.4.2:503c0ab8-133f-455f-b07d-53364dbfead5".split(
            ":"
        ),
    ].copy()


@pytest.fixture
def mock_director_service(
    model_fake_factory,
    running_service_model_schema,
    registry_service_model_schema,
    user_id: int,
    project_id: str,
    project_nodes: list[tuple[str, ...]],
):
    # helpers
    def fake_registry_service_model(**overrides):
        return model_fake_factory(registry_service_model_schema, **overrides)

    def fake_running_service_model(**overrides):
        return model_fake_factory(running_service_model_schema, **overrides)

    # fake director service "state" variables
    _fake_project_services = [
        fake_registry_service_model(key=s[0], version=s[1]) for s in project_nodes
    ]

    _fake_running_services = []

    def _get_running():
        return [
            s
            for s in _fake_running_services
            if s["service_state"] not in "complete failed".split()
        ]

    #
    # Mocks director's service API  api/specs/director/openapi.yaml
    #
    with aioresponses() as mock:
        # GET /running_interactive_services -------------------------------------------------
        url_pattern = (
            r"^http://[a-z\-_]*director:[0-9]+/v0/running_interactive_services\?.*$"
        )

        def get_running_interactive_services_handler(url: URL, **kwargs):
            assert int(url.query.get("user_id", 0)) in (user_id, 0)
            assert url.query.get("project_id") in (project_id, None)

            return CallbackResult(payload={"data": _get_running()}, status=200)

        mock.get(
            re.compile(url_pattern),
            callback=get_running_interactive_services_handler,
            repeat=True,
        )

        # POST /running_interactive_services -------------------------------------------------

        url_pattern = (
            r"^http://[a-z\-_]*director:[0-9]+/v0/running_interactive_services\?.*$"
        )

        def start_service_handler(url: URL, **kwargs):
            assert int(url.query["user_id"]) == user_id
            assert url.query["project_id"] == project_id

            service_uuid = url.query["service_uuid"]

            if any(s["service_uuid"] == service_uuid for s in _get_running()):
                return CallbackResult(
                    payload={
                        "error": f"A service with the same uuid {service_uuid} already running exists"
                    },
                    status=409,
                )

            service_key = url.query["service_key"]
            service_tag = url.query.get("service_tag")

            try:
                service = next(
                    s
                    for s in _fake_project_services
                    if s["key"] == service_key and s["version"] == service_tag
                )
            except StopIteration:
                return CallbackResult(
                    payload={
                        "error": f"Service {service_key}:{service_tag} not found in project"
                    },
                    status=404,
                )

            starting_service = fake_running_service_model(
                service_key=service["key"],
                service_version=service["version"],
                service_basepath=url.query.get(
                    "service_basepath", ""
                ),  # predefined basepath for the backend service otherwise uses root
                service_state="starting",  # let's assume it pulls very fast :-)
            )

            _fake_running_services.append(starting_service)
            return CallbackResult(payload={"data": starting_service}, status=201)

        mock.post(re.compile(url_pattern), callback=start_service_handler, repeat=True)

        # DELETE /running_interactive_services/{service_uuid}-------------------------------------------------
        url_pattern = (
            r"^http://[a-z\-_]*director:[0-9]+/v0/running_interactive_services/.+$"
        )

        def stop_service_handler(url: URL, **kwargs):
            service_uuid = url.parts[-1]
            required_query_parameter = "save_state"
            if required_query_parameter not in kwargs["params"]:
                return CallbackResult(
                    payload={
                        "error": f"stop_service endpoint was called without query parameter {required_query_parameter} {url}"
                    },
                    status=500,
                )

            try:
                service = next(
                    s
                    for s in _fake_running_services
                    if s["service_uuid"] == service_uuid
                )
                service["service_state"] = "complete"

            except StopIteration:
                return CallbackResult(
                    payload={"error": "service not found"}, status=404
                )

            return CallbackResult(status=204)

        mock.delete(re.compile(url_pattern), callback=stop_service_handler, repeat=True)

        # GET /services/{service_key}/{service_version}-------------------------------------------------
        url_pattern = r"^http://[a-z\-_]*director:[0-9]+/v0/services/.+/.+$"

        def get_service_by_key_version_handler(url: URL, **kwargs):
            service_key, service_version = url.parts[-2:]
            # TODO: validate against schema?
            # TODO: improve API: does it make sense to return multiple services
            services = [
                s
                for s in _fake_project_services
                if s["key"] == service_key and s["version"] == service_version
            ]
            if services:
                return CallbackResult(payload={"data": services}, status=200)

            return CallbackResult(
                payload={
                    "error": f"Service {service_key}:{service_version} not found in project"
                },
                status=404,
            )

        mock.get(
            re.compile(url_pattern),
            callback=get_service_by_key_version_handler,
            repeat=True,
        )

        # GET /service_extras/{service_key}/{service_version}
        # get_service_extras = re.compile(
        #    r"^http://[a-z\-_]*director:[0-9]+/v0/service_extras/\w+/.+$"
        # )

        ## mock.get(get_service_extras, status=200, payload={"data": {}})
        yield mock


@pytest.fixture
def app_mock(mock_env_devel_environment):
    cfg = {"director": {"enabled": True}}
    app = create_safe_application(cfg)
    setup_settings(app)
    assert setup_director(app)

    return app


def test_director_openapi_specs(director_openapi_specs):
    #
    # At this point in time we cannot afford a more sophisticated way to
    # do it so we resign ourselves to doing it by hand
    #
    assert "get" in director_openapi_specs["paths"]["/running_interactive_services"]
    assert "post" in director_openapi_specs["paths"]["/running_interactive_services"]

    assert (
        "delete"
        in director_openapi_specs["paths"][
            "/running_interactive_services/{service_uuid}"
        ]
    )
    assert (
        "get"
        in director_openapi_specs["paths"][
            "/running_interactive_services/{service_uuid}"
        ]
    )


async def test_director_workflow(
    mock_director_service,
    app_mock,
    user_id: int,
    project_id: str,
    project_nodes: list[tuple[str, ...]],
):
    app = app_mock

    # After app's setup, the director config should be in place
    # and all these function should trigger requests correclty
    # to the director service
    #
    # These tests will capture those requests in the back at the transport
    # layer and make sure they comply with OpenApi specifications of the
    # director's API
    #

    # nothing is running
    running_services = await get_running_interactive_services(
        app, str(user_id), project_id
    )
    assert not running_services

    for service_key, service_version, service_uuid in project_nodes:
        # service is in registry
        service = await get_service_by_key_version(app, service_key, service_version)
        assert service

        # not running
        running_services = await get_running_interactive_services(
            app, str(user_id), project_id
        )
        assert not any(s["service_uuid"] == service_uuid for s in running_services)

        # start
        started = await start_service(
            app,
            str(user_id),
            project_id,
            service_key,
            service_version,
            service_uuid,
            "localhost",
            "http",
            "test",
        )

        # now is running
        running_services = await get_running_interactive_services(
            app, str(user_id), project_id
        )
        assert started in running_services

    # so two of them are running
    running_services = await get_running_interactive_services(
        app, str(user_id), project_id
    )
    assert len(running_services) == 2

    # stop all
    await stop_services(app, user_id=str(user_id))  # also calls stop_service

    # nothing running
    running_services = await get_running_interactive_services(
        app, str(user_id), project_id
    )
    assert not running_services
