# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import os
import time
from pprint import pformat
from typing import Any, Callable, Dict, List

import httpx
import osparc
import pytest
from osparc.configuration import Configuration
from tenacity import Retrying, before_sleep_log, stop_after_attempt, wait_fixed

log = logging.getLogger(__name__)


pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.tmp_path_extra",
]


@pytest.fixture(scope="session")
def testing_environ_vars(testing_environ_vars: Dict[str, str]) -> Dict[str, str]:
    ## OVERRIDES packages/pytest-simcore/src/pytest_simcore/docker_compose.py::testing_environ_vars fixture

    # help faster update of service_metadata table by catalog
    testing_environ_vars["CATALOG_BACKGROUND_TASK_REST_TIME"] = "1"
    return testing_environ_vars.copy()


@pytest.fixture(scope="module")
def core_services_selection(simcore_docker_compose: Dict) -> List[str]:
    """ Selection of services from the simcore stack """
    ## OVERRIDES packages/pytest-simcore/src/pytest_simcore/docker_compose.py::core_services_selection fixture
    all_core_services = list(simcore_docker_compose["services"].keys())
    return all_core_services


@pytest.fixture(scope="module")
def ops_services_selection(ops_docker_compose: Dict) -> List[str]:
    """ Selection of services from the ops stack """
    ## OVERRIDES packages/pytest-simcore/src/pytest_simcore/docker_compose.py::ops_services_selection fixture
    all_ops_services = list(ops_docker_compose["services"].keys())
    return all_ops_services


@pytest.fixture(scope="module")
def simcore_docker_stack_and_registry_ready(
    docker_stack: Dict,
    docker_registry,
) -> Dict:

    for attempt in Retrying(
        wait=wait_fixed(5),
        stop=stop_after_attempt(60),
        reraise=True,
        before_sleep=before_sleep_log(log, logging.INFO),
    ):
        with attempt:
            resp = httpx.get("http://127.0.0.1:9081/v0/")
            resp.raise_for_status()

    return docker_stack


@pytest.fixture(scope="module")
def registered_user(simcore_docker_stack_and_registry_ready):
    user = {
        "email": "first.last@mymail.com",
        "password": "my secret",
        "api_key": None,
        "api_secret": None,
    }

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

        user.update({"api_key": data["api_key"], "api_secret": data["api_secret"]})

        yield user

        resp = client.request(
            "DELETE", "/auth/api-keys", json={"display_name": "test-public-api"}
        )


@pytest.fixture(scope="module")
def services_registry(
    docker_registry_image_injector: Callable,
    registered_user: Dict[str, str],
    testing_environ_vars: Dict[str, str],
) -> Dict[str, Any]:
    # NOTE: service image MUST be injected in registry AFTER user is registered
    #
    # See injected fixture in packages/pytest-simcore/src/pytest_simcore/docker_registry.py
    #
    user_email = registered_user["email"]

    sleeper_service = docker_registry_image_injector(
        "itisfoundation/sleeper", "2.1.1", user_email
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
                "description": "Pick a file containing only one " "integer",
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
                "description": "It will first walk the distance to " "bed",
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
                "description": "Interval is generated in range " "[1-9]",
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
        testing_environ_vars["CATALOG_BACKGROUND_TASK_REST_TIME"]
    )
    print(
        f"Catalog should take {wait_for_catalog_to_detect} secs to detect new services ...",
    )
    time.sleep(wait_for_catalog_to_detect)

    return {
        "sleeper_service": {
            "name": sleeper_service["image"]["name"],
            "version": sleeper_service["image"]["tag"],
            "schema": sleeper_service["schema"],
        },
        # add here more
    }


@pytest.fixture(scope="module")
def api_client(registered_user) -> osparc.ApiClient:
    cfg = Configuration(
        host=os.environ.get("OSPARC_API_URL", "http://127.0.0.1:8006"),
        username=registered_user["api_key"],
        password=registered_user["api_secret"],
    )

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
def files_api(api_client) -> osparc.FilesApi:
    return osparc.FilesApi(api_client)


@pytest.fixture(scope="module")
def solvers_api(api_client, services_registry) -> osparc.SolversApi:
    # services_registry fixture dependency ensures that services are injected in registry
    return osparc.SolversApi(api_client)
