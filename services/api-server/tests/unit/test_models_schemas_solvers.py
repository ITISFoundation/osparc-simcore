# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from operator import attrgetter

from faker import Faker
from simcore_service_api_server.models.schemas.solvers import Solver, Version


def test_solvers_sorting_by_name_and_version(faker: Faker):
    # SEE https://packaging.pypa.io/en/latest/version.html

    # have a solver
    one_solver = Solver(**Solver.model_config["json_schema_extra"]["example"])

    assert isinstance(one_solver.pep404_version, Version)
    major, minor, micro = one_solver.pep404_version.release
    one_solver.version = f"{major}.{minor}.{micro}"

    # and a different version of the same
    # NOTE: that id=None so that it can be re-coputed
    earlier_release = one_solver.model_copy(
        update={"version": f"{one_solver.version}beta"}, deep=True
    )
    assert earlier_release.pep404_version.is_prerelease
    assert earlier_release.pep404_version < one_solver.pep404_version

    # and yet a completely different solver
    another_solver = one_solver.model_copy(
        update={"id": "simcore/services/comp/zSolve"}
    )
    assert one_solver.id != another_solver.id
    assert one_solver.pep404_version == another_solver.pep404_version

    # let's sort a list of solvers by name and then by version
    sorted_solvers = sorted(
        [one_solver, another_solver, earlier_release],
        key=attrgetter("id", "pep404_version"),
    )

    assert [s.name for s in sorted_solvers] == [
        earlier_release.name,
        one_solver.name,
        another_solver.name,
    ]
