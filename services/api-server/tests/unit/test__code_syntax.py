# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from uuid import UUID

import pytest
from faker import Faker
from fastapi import APIRouter, FastAPI, status
from fastapi.testclient import TestClient
from pytest_simcore.helpers.utils_pylint import (
    assert_no_pdb_in_code,
    assert_pylint_is_passing,
)
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
    the_app.include_router(router, prefix="/v0")

    return TestClient(the_app)


def test_fastapi_route_name_parsing(client: TestClient, faker: Faker):
    #
    # This is a fast test for compatibility.
    # Will help in early detection of issues when fastapi library is upgraded
    #

    solver_key = Solver.Config.schema_extra["example"]["id"]
    version = Solver.Config.schema_extra["example"]["version"]
    job_id = faker.uuid4()

    # Checks whether parse correctly ":action" suffix
    for action in ("start", "stop"):
        expected_path = client.app.router.url_path_for(
            f"{action}_job", solver_key=solver_key, version=version, job_id=job_id
        )
        resp = client.post(
            f"/v0/solvers/{solver_key}/releases/{version}/jobs/{job_id}:{action}"
        )
        assert resp.url.endswith(expected_path)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["action"] == f"{action}_job"

    resp = client.get(f"/v0/solvers/{solver_key}/releases/{version}/jobs/{job_id}")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["action"] == "get_job"


def test_run_pylint(pylintrc, package_dir):
    # fixtures in pytest_simcore.environs
    assert_pylint_is_passing(pylintrc=pylintrc, package_dir=package_dir)


def test_no_pdbs_in_place(package_dir):
    # fixtures in pytest_simcore.environs
    assert_no_pdb_in_code(code_dir=package_dir)
