# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import json
import logging
import os
import time
from collections.abc import Callable, Iterable, Iterator
from pprint import pformat

import httpx
import osparc
import pytest
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from pytest_simcore.helpers.typing_docker import UrlStr
from pytest_simcore.helpers.typing_public_api import (
    RegisteredUserDict,
    ServiceInfoDict,
    ServiceNameStr,
    StacksDeployedDict,
)
from tenacity import Retrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

_logger = logging.getLogger(__name__)


_MINUTE: int = 60  # in secs


pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.simcore_services",
]


@pytest.fixture(scope="session")
def env_vars_for_docker_compose(
    env_vars_for_docker_compose: EnvVarsDict,
) -> EnvVarsDict:
    # OVERRIDES packages/pytest-simcore/src/pytest_simcore/docker_compose.py::env_vars_for_docker_compose fixture

    # help faster update of service_metadata table by catalog
    env_vars_for_docker_compose["CATALOG_BACKGROUND_TASK_REST_TIME"] = "1"
    return env_vars_for_docker_compose.copy()


@pytest.fixture(scope="module")
def core_services_selection(simcore_docker_compose: dict) -> list[str]:
    """Selection of services from the simcore stack"""
    # OVERRIDES packages/pytest-simcore/src/pytest_simcore/docker_compose.py::core_services_selection fixture
    all_core_services = list(simcore_docker_compose["services"].keys())
    return all_core_services


@pytest.fixture(scope="module")
def ops_services_selection(ops_docker_compose: dict) -> list[str]:
    """Selection of services from the ops stack"""
    # OVERRIDES packages/pytest-simcore/src/pytest_simcore/docker_compose.py::ops_services_selection fixture
    all_ops_services = list(ops_docker_compose["services"].keys())
    if "CI" in os.environ:
        all_ops_services = ["minio"]
        print(f"WARNING: Only required services will be started {all_ops_services=}")
    return all_ops_services


@pytest.fixture(scope="module")
def event_loop(request: pytest.FixtureRequest) -> Iterable[asyncio.AbstractEventLoop]:
    """Overrides pytest_asyncio.event_loop and extends to module scope"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def simcore_docker_stack_and_registry_ready(
    event_loop: asyncio.AbstractEventLoop,
    docker_registry: UrlStr,
    docker_stack: StacksDeployedDict,
    simcore_services_ready_module: None,
) -> StacksDeployedDict:
    # At this point `simcore_services_ready` waited until all services
    # are running. Let's make one more check on the web-api
    for attempt in Retrying(
        wait=wait_fixed(1),
        stop=stop_after_delay(0.5 * _MINUTE),
        reraise=True,
        before_sleep=before_sleep_log(_logger, logging.INFO),
    ):
        with attempt:
            resp = httpx.get("http://127.0.0.1:9081/v0/")
            resp.raise_for_status()
            _logger.info(
                "Connection to osparc-simcore web API succeeded [%s]",
                json.dumps(attempt.retry_state.retry_object.statistics),
            )

    return docker_stack


@pytest.fixture(scope="module")
def registered_user(
    simcore_docker_stack_and_registry_ready: StacksDeployedDict,
) -> Iterator[RegisteredUserDict]:
    first_name = "john"
    last_name = "smith"
    user = RegisteredUserDict(
        # NOTE: keep these conventions to make test simpler
        first_name=first_name.lower(),
        last_name=last_name.lower(),
        email=f"{first_name}.{last_name}@company.com".lower(),
        password="alongpasswordthatisnotweak",
        api_key="",
        api_secret="",
    )

    with httpx.Client(base_url="http://127.0.0.1:9081/v0") as client:
        # setup user via web-api
        resp = client.post(
            "/auth/login",
            json={
                "email": user["email"],
                "password": user["password"],
            },
        )

        if resp.status_code != 200:
            resp = client.post(
                "/auth/register",
                json={
                    "email": user["email"],
                    "password": user["password"],
                    "confirm": user["password"],
                },
            )
            resp.raise_for_status()

        # create a key via web-api
        resp = client.post("/auth/api-keys", json={"display_name": "test-public-api"})

        print(resp.text)
        resp.raise_for_status()

        data = resp.json()["data"]
        assert data["display_name"] == "test-public-api"

        assert "api_key" in data
        assert "api_secret" in data

        user["api_key"] = data["api_key"]
        user["api_secret"] = data["api_secret"]

        yield user

        resp = client.request(
            "DELETE", "/auth/api-keys", json={"display_name": "test-public-api"}
        )


@pytest.fixture(scope="module")
def services_registry(
    docker_registry_image_injector: Callable,
    registered_user: RegisteredUserDict,
    env_vars_for_docker_compose: dict[str, str],
) -> dict[ServiceNameStr, ServiceInfoDict]:
    # NOTE: service image MUST be injected in registry AFTER user is registered
    #
    # See injected fixture in packages/pytest-simcore/src/pytest_simcore/docker_registry.py
    #
    user_email = registered_user["email"]

    sleeper_service = docker_registry_image_injector(
        source_image_repo="itisfoundation/sleeper",
        source_image_tag="2.1.1",
        owner_email=user_email,
    )

    assert sleeper_service["image"]["tag"] == "2.1.1"
    assert sleeper_service["image"]["name"] == "simcore/services/comp/itis/sleeper"
    assert sleeper_service["schema"] == {
        "authors": [
            {"name": "Tester", "email": user_email, "affiliation": "IT'IS Foundation"}
        ],
        "contact": user_email,
        "description": "A service which awaits for time to pass, two times.",
        "inputs": {
            "input_1": {
                "description": "Pick a file containing only one integer",
                "displayOrder": 1,
                "fileToKeyMap": {"single_number.txt": "input_1"},
                "label": "File with int number",
                "type": "data:text/plain",
            },
            "input_2": {
                "defaultValue": 2,
                "description": "Choose an amount of time to sleep",
                "displayOrder": 2,
                "label": "Sleep interval",
                "type": "integer",
                "unit": "second",
            },
            "input_3": {
                "defaultValue": False,
                "description": "If set to true will cause service to "
                "fail after it sleeps",
                "displayOrder": 3,
                "label": "Fail after sleep",
                "type": "boolean",
            },
            "input_4": {
                "defaultValue": 0,
                "description": "It will first walk the distance to bed",
                "displayOrder": 4,
                "label": "Distance to bed",
                "type": "integer",
                "unit": "meter",
            },
        },
        "integration-version": "1.0.0",
        "key": "simcore/services/comp/itis/sleeper",
        "name": "sleeper",
        "outputs": {
            "output_1": {
                "description": "Integer is generated in range [1-9]",
                "displayOrder": 1,
                "fileToKeyMap": {"single_number.txt": "output_1"},
                "label": "File containing one random integer",
                "type": "data:text/plain",
            },
            "output_2": {
                "description": "Interval is generated in range [1-9]",
                "displayOrder": 2,
                "label": "Random sleep interval",
                "type": "integer",
                "unit": "second",
            },
        },
        "type": "computational",
        "version": "2.1.1",
    }

    wait_for_catalog_to_detect = float(
        env_vars_for_docker_compose["CATALOG_BACKGROUND_TASK_REST_TIME"]
    )
    print(
        f"Catalog should take {wait_for_catalog_to_detect} secs to detect new services ...",
    )
    time.sleep(wait_for_catalog_to_detect + 1)

    return {
        "sleeper_service": ServiceInfoDict(
            name=sleeper_service["image"]["name"],
            version=sleeper_service["image"]["tag"],
            schema=sleeper_service["schema"],
        ),
        # add here more
    }


@pytest.fixture(scope="module")
def api_client(
    registered_user: RegisteredUserDict,
) -> Iterator[osparc.ApiClient]:
    cfg = osparc.Configuration(
        host=os.environ.get("OSPARC_API_URL", "http://127.0.0.1:8006"),
        username=registered_user["api_key"],
        password=registered_user["api_secret"],
    )

    print("Configuration:", cfg.to_debug_report())

    def as_dict(obj: object):
        return {
            attr: getattr(obj, attr)
            for attr in obj.__dict__.keys()
            if not attr.startswith("_")
        }

    print("cfg", pformat(as_dict(cfg)))

    with osparc.ApiClient(cfg) as api_client:
        yield api_client


@pytest.fixture(scope="module")
def files_api(api_client: osparc.ApiClient) -> osparc.FilesApi:
    return osparc.FilesApi(api_client)


@pytest.fixture(scope="module")
def solvers_api(
    api_client: osparc.ApiClient,
    services_registry: dict[ServiceNameStr, ServiceInfoDict],
) -> osparc.SolversApi:
    # services_registry fixture dependency ensures that services are injected in registry
    return osparc.SolversApi(api_client)
