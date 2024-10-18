# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
"""
This is a light compatibilty test to check some expected features on fastapi

These tests aim to detect changes in some selected feature specs after upgrades of fastapi
or related libraries.

After some dependency upgrades some of the features tested belowed changed
specs which caused tests/public-api to fail. Changes were indeed detected but
`tests/public-api` are heavy system testing and made the debugging and discovery
of the problem very time consuming.

By adding these checks we intend to mitigate this problem by providing a fast
and early detection of changes in the specs of selected features
when fastapi or related libraries are upgraded.
"""

import urllib
import urllib.parse
from uuid import UUID

import pytest
from faker import Faker
from fastapi import APIRouter, FastAPI, status
from fastapi.testclient import TestClient
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.solvers import (
    Solver,
    SolverKeyId,
    VersionStr,
)


@pytest.fixture
def client() -> TestClient:
    # overrides client.
    # WARNING: this is NOT httpx.AsyncClient

    router = APIRouter(prefix="/solvers")

    @router.get("/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}")
    async def get_job(
        solver_key: SolverKeyId,
        version: VersionStr,
        job_id: UUID,
    ):
        return {
            "action": get_job.__name__,
            "solver_key": solver_key,
            "version": version,
            "job_id": job_id,
        }

    @router.post("/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}:start")
    async def start_job(
        solver_key: SolverKeyId,
        version: VersionStr,
        job_id: UUID,
    ):
        return {
            "action": start_job.__name__,
            "solver_key": solver_key,
            "version": version,
            "job_id": job_id,
        }

    @router.post("/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}:stop")
    async def stop_job(
        solver_key: SolverKeyId,
        version: VersionStr,
        job_id: UUID,
    ):
        return {
            "action": stop_job.__name__,
            "solver_key": solver_key,
            "version": version,
            "job_id": job_id,
        }

    the_app = FastAPI()
    the_app.include_router(router, prefix=f"/{API_VTAG}")

    return TestClient(the_app)


def test_fastapi_route_paths_in_paths(client: TestClient, faker: Faker):
    solver_key = "simcore/services/comp/itis/isolve"
    version = "1.2.3"
    job_id = faker.uuid4()

    # can be raw
    raw_solver_key = solver_key
    resp = client.get(
        f"/{API_VTAG}/solvers/{raw_solver_key}/releases/{version}/jobs/{job_id}"
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {
        "action": "get_job",
        "solver_key": solver_key,
        "version": version,
        "job_id": job_id,
    }

    # can be quoted
    quoted_solver_key = urllib.parse.quote_plus("simcore/services/comp/itis/isolve")
    resp = client.get(
        f"/{API_VTAG}/solvers/{quoted_solver_key}/releases/{version}/jobs/{job_id}"
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {
        "action": "get_job",
        "solver_key": solver_key,
        "version": version,
        "job_id": job_id,
    }


def test_fastapi_route_name_parsing(client: TestClient, app: FastAPI, faker: Faker):
    #
    # Ensures ':' is allowed in routes
    # SEE https://github.com/encode/starlette/pull/1657

    solver_key = Solver.model_config["json_schema_extra"]["example"]["id"]
    version = Solver.model_config["json_schema_extra"]["example"]["version"]
    job_id = faker.uuid4()

    # Checks whether parse correctly ":action" suffix
    for action in ("start", "stop"):
        expected_path = app.router.url_path_for(
            f"{action}_job", solver_key=solver_key, version=version, job_id=job_id
        )
        resp = client.post(
            f"/{API_VTAG}/solvers/{solver_key}/releases/{version}/jobs/{job_id}:{action}"
        )
        assert resp.url.path == expected_path
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["action"] == f"{action}_job"

    resp = client.get(
        f"/{API_VTAG}/solvers/{solver_key}/releases/{version}/jobs/{job_id}"
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["action"] == "get_job"
