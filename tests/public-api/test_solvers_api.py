# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import random
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple

import pytest
from osparc.api.solvers_api import SolversApi
from osparc.exceptions import ApiException
from osparc.models import Solver
from packaging.version import parse as parse_version


@pytest.fixture
def sleeper_key_and_version(services_registry: Dict[str, Any]) -> Tuple[str, str]:
    # image in registry
    repository_name = services_registry["sleeper_service"]["name"]
    tag = services_registry["sleeper_service"]["version"]

    # this is how image info map into solvers identifiers
    #
    #  repository_name -> solver_key
    #  tag -> version
    #
    return repository_name, tag


def test_get_latest_solver(solvers_api: SolversApi):
    solvers: List[Solver] = solvers_api.list_solvers()  # latest versions of all solvers

    solver_names = []
    for latest in solvers:
        assert solvers_api.get_solver_release(latest.id, latest.version) == latest

        solver_names.append(latest.id)

    assert sorted(solver_names) == sorted(set(solver_names))


def test_get_all_releases(solvers_api: SolversApi):

    all_releases: List[
        Solver
    ] = solvers_api.list_solvers_releases()  # all release of all solvers

    one_solver = random.choice(all_releases)
    all_releases_of_given_solver: List[Solver] = solvers_api.list_solver_releases(
        one_solver.id
    )

    latest: Optional[Solver] = None
    for solver in all_releases_of_given_solver:
        if one_solver.id == solver.id:
            assert isinstance(solver, Solver)

            if not latest:
                latest = solver

            elif parse_version(latest.version) < parse_version(solver.version):
                latest = solvers_api.get_solver_release(solver.id, solver.version)

    print(latest)
    assert latest
    assert latest == all_releases_of_given_solver[-1]


def test_get_solver_release(solvers_api: SolversApi, sleeper_key_and_version):
    expected_solver_key, expected_version = sleeper_key_and_version

    solver = solvers_api.get_solver_release(
        solver_key=expected_solver_key, version=expected_version
    )

    assert solver.id == expected_solver_key
    assert solver.version == expected_version

    same_solver = solvers_api.get_solver(solver.id)  # latest

    assert same_solver.id == solver.id
    assert same_solver.version == solver.version

    # FIXME: same uuid returns different maintainer, title and description (probably bug in catalog since it shows "nodetails" tags)
    assert solver == same_solver


def test_solvers_not_found(solvers_api):

    with pytest.raises(ApiException) as excinfo:
        solvers_api.get_solver_release(
            "simcore/services/comp/something-not-in-this-registry",
            "1.4.55",
        )
    assert excinfo.value.status == HTTPStatus.NOT_FOUND  # 404
    assert "not found" in excinfo.value.reason.lower()
