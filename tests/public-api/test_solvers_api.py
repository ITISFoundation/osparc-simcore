# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import random
from http import HTTPStatus
from typing import NamedTuple

import osparc
import pytest
from packaging.version import parse as parse_version
from pytest_simcore.helpers.utils_public_api import ServiceInfoDict, ServiceNameStr


class NameTagTuple(NamedTuple):
    repository_name: str
    tag: str


@pytest.fixture(scope="module")
def sleeper_key_and_version(
    services_registry: dict[ServiceNameStr, ServiceInfoDict]
) -> NameTagTuple:
    # image in registry
    repository_name = services_registry["sleeper_service"]["name"]
    tag = services_registry["sleeper_service"]["version"]

    assert repository_name == "simcore/services/comp/itis/sleeper"
    assert tag == "2.1.1"
    # this is how image info map into solvers identifiers
    #
    #  repository_name -> solver_key
    #  tag -> version
    #
    return NameTagTuple(repository_name, tag)


def test_get_latest_solver(solvers_api: osparc.SolversApi):
    solvers: list[
        osparc.Solver
    ] = solvers_api.list_solvers()  # latest versions of all solvers

    solver_names = []
    for latest in solvers:
        assert solvers_api.get_solver_release(latest.id, latest.version) == latest

        solver_names.append(latest.id)

    assert solver_names
    assert sorted(solver_names) == sorted(set(solver_names))


def test_get_all_releases(solvers_api: osparc.SolversApi):

    all_releases: list[
        osparc.Solver
    ] = solvers_api.list_solvers_releases()  # all release of all solvers

    assert all_releases

    one_solver = random.choice(all_releases)
    all_releases_of_given_solver: list[
        osparc.Solver
    ] = solvers_api.list_solver_releases(one_solver.id)

    latest: osparc.Solver | None = None
    for solver in all_releases_of_given_solver:
        if one_solver.id == solver.id:
            assert isinstance(solver, osparc.Solver)

            if not latest:
                latest = solver

            elif parse_version(latest.version) < parse_version(solver.version):
                latest = solvers_api.get_solver_release(solver.id, solver.version)

    print(latest)
    assert latest
    assert latest == all_releases_of_given_solver[-1]


def test_get_solver_release(
    solvers_api: osparc.SolversApi, sleeper_key_and_version: NameTagTuple
):
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


def test_solvers_not_found(solvers_api: osparc.SolversApi):

    with pytest.raises(osparc.ApiException) as excinfo:
        solvers_api.get_solver_release(
            "simcore/services/comp/something-not-in-this-registry",
            "1.4.55",
        )
    assert excinfo.value.status == HTTPStatus.NOT_FOUND  # 404
    assert "not found" in excinfo.value.reason.lower()
