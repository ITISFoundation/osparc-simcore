# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from typing import List

import osparc
import pytest
from osparc.models import Solver
from packaging.version import parse as parse_version


@pytest.fixture()
def solvers_api(api_client):
    return osparc.SolversApi(api_client)


def test_solvers(solvers_api):
    solvers: List[Solver] = solvers_api.list_solvers()

    latest = None
    for solver in solvers:
        if "sleeper" in solver.name:
            assert isinstance(solver, Solver)

            if not latest:
                latest = solver

            elif parse_version(latest.version) < parse_version(solver.version):
                latest = solvers_api.get_solver_by_id(solver.id)

    print(latest)
    assert latest

    assert (
        solvers_api.get_solver_by_name_and_version(
            solver_name=latest.name, version="latest"
        )
        == latest
    )

    # FIXME: same uuid returns different maintener, title and description (probably bug in catalog since it shows "nodetails" tags)
    # assert solvers_api.get_solver(latest.id) == latest
