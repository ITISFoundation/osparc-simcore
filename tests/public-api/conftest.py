# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import os
import sys
from pathlib import Path
from pprint import pformat
from typing import Any, Dict

import httpx
import osparc
import pytest
from osparc.configuration import Configuration
from tenacity import Retrying, before_sleep_log, stop_after_attempt, wait_fixed

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
log = logging.getLogger(__name__)


pytest_plugins = [
    "pytest_simcore.repository_paths",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.docker_registry",
    "pytest_simcore.schemas",
]


@pytest.fixture(scope="module")
def prepare_all_services(
    simcore_docker_compose: Dict,
    ops_docker_compose: Dict,
    request,
) -> Dict:

    setattr(
        request.module, "core_services", list(simcore_docker_compose["services"].keys())
    )
    core_services = getattr(request.module, "core_services", [])

    setattr(request.module, "ops_services", list(ops_docker_compose["services"].keys()))
    ops_services = getattr(request.module, "ops_services", [])

    services = {"simcore": simcore_docker_compose, "ops": ops_docker_compose}
    return services


@pytest.fixture(scope="module")
def services_registry(sleeper_service) -> Dict[str, Any]:
    # See other service fixtures in
    # packages/pytest-simcore/src/pytest_simcore/docker_registry.py
    return {
        "sleeper_service": {
            "name": sleeper_service["image"]["name"],
            "version": sleeper_service["image"]["tag"],
            "schema": sleeper_service["schema"],
        },
        # add here more
    }


@pytest.fixture(scope="module")
def make_up_prod(
    prepare_all_services: Dict,
    simcore_docker_compose: Dict,
    ops_docker_compose: Dict,
    docker_stack: Dict,
    services_registry,
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

    stack_configs = {"simcore": simcore_docker_compose, "ops": ops_docker_compose}
    return stack_configs


@pytest.fixture(scope="module")
def registered_user():
    # def registered_user(make_up_prod):

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


@pytest.fixture
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


@pytest.fixture()
def files_api(api_client) -> osparc.FilesApi:
    return osparc.FilesApi(api_client)


@pytest.fixture()
def solvers_api(api_client):
    return osparc.SolversApi(api_client)
