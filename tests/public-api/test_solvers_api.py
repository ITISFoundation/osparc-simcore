# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from http import HTTPStatus
from typing import List

import pytest
from osparc.exceptions import ApiException
from osparc.models import Solver
from packaging.version import parse as parse_version


def test_get_latest_solver(solvers_api):
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


def test_get_solver(solvers_api, expected_):
    solver = solvers_api.get_solver_by_name_and_version(
        solver_name="simcore/services/comp/itis/sleeper", version="1.0.0"
    )

    assert solver.name == "simcore/services/comp/itis/sleeper"
    assert solver.version == "1.0.0"

    same_solver = solvers_api.get_solver_by_id(solver.id)

    assert same_solver.id == solver.id
    assert same_solver.name == solver.name
    assert same_solver.version == solver.version

    # FIXME: same uuid returns different maintener, title and description (probably bug in catalog since it shows "nodetails" tags)
    assert solver == same_solver


def test_solvers_not_found(solvers_api):

    with pytest.raises(ApiException) as excinfo:
        solvers_api.get_solver_by_name_and_version(
            solver_name="simcore/services/comp/something-not-in-this-registry",
            version="1.4.55",
        )
    assert excinfo.errisinstance.status == HTTPStatus.NOT_FOUND  # 404
    assert "solver" in excinfo.errisinstance.reason.lower()
