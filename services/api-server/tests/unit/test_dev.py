# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import uuid
from datetime import datetime, timedelta

import httpx
import pytest
from simcore_service_api_server.api.routes.solvers import compose_solver_id
from simcore_service_api_server.models.schemas.solvers import (
    Solver,
    SolverOverview,
    SolverRelease,
)

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


def test_id_composer():
    u = compose_solver_id("comp", 1)
    assert u.variant == uuid.RFC_4122
    assert u.version == 3
    ##assert str(u) ==


def create_solver(key):
    return Solver(
        solver_key=key,
        title="S4L isolve",
        maintainer="pcrespov",
        releases=[
            SolverRelease(
                solver_id=compose_solver_id(key, "1.0.1"),
                version="1.0.1",
                version_alias=["1", "1.0", "latest"],
                release_date=datetime.now(),
            ),
            SolverRelease(
                solver_id=compose_solver_id(key, "1.0.0"),
                version="1.0.0",
                release_date=datetime.now() - timedelta(days=1),
            ),
        ],
    )


SOLVERS = [
    create_solver("simcore/services/comp/isolve"),
    create_solver("simcore/services/comp/mpi-isolve"),
]


SOLVERS_OVERVIEW = [
    SolverOverview(
        latest_version=s.releases[0].version,
        solver_url=f"http://foo.com/v0/solvers/{s.releases[0].solver_id}",
        **s.dict(include={"solver_key", "title", "maintainer"}),
    )
    for s in SOLVERS
]


def disable__test_it():

    # list solvers
    latest_solvers = [s.dict(exclude_none=True) for s in SOLVERS_OVERVIEW]

    # select a solver

    # run with input

    # check status

    # get outputs


@pytest.fixture
async def cli():
    async with httpx.AsyncClient(base_url="http://localhost:8000/v0") as client:
        yield client

@pytest.mark.skip(reason="DEV")
async def test_it(cli):
    r = await cli.get("/meta")
    assert r.json() == {
        "name": "simcore_service_api_server",
        "version": "0.3.0",
        "released": {"v0": "0.3.0"},
    }
