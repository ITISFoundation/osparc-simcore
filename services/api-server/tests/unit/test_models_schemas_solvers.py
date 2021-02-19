# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from operator import attrgetter
from pprint import pformat

import pytest
from simcore_service_api_server.api.routes.solvers_faker import SolversFaker
from simcore_service_api_server.models.schemas.jobs import (
    Job,
    JobInput,
    JobOutput,
    _compose_job_id,
)
from simcore_service_api_server.models.schemas.solvers import Solver, Version


@pytest.mark.parametrize("model_cls", (Job, Solver, JobInput, JobOutput))
def test_solvers_model_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


def test_create_solver_from_image_metadata():
    for image_metadata in SolversFaker.load_images():
        solver = Solver.create_from_image(image_metadata)
        print(solver.json(indent=2))

        assert solver.id is not None, "should be auto-generated"
        assert solver.url is None


def test_create_job_model():
    job = Job.create_now("solvers/isolve/releases/1.3.4", "12345")

    print(job.json(indent=2))
    assert job.id is not None

    # pylint: disable=no-value-for-parameter
    max_cached_bytes = sys.getsizeof(job.id) * _compose_job_id.cache_info().maxsize
    assert max_cached_bytes < 1024 * 1024, "Cache expected < 1MB, reduce maxsize"

    # TODO: https://stackoverflow.com/questions/5802108/how-to-check-if-a-datetime-object-is-localized-with-pytz/27596917
    # TODO: @validator("created_at", always=True)
    # def ensure_utc(cls, v):
    #    v.utc


def test_solvers_sorting_by_name_and_version(faker):
    # SEE https://packaging.pypa.io/en/latest/version.html

    # have a solver
    one_solver = Solver(**Solver.Config.schema_extra["example"])

    assert isinstance(one_solver.pep404_version, Version)
    major, minor, micro = one_solver.pep404_version.release
    one_solver.version = f"{major}.{minor}.{micro}"

    # and a different version of the same
    # NOTE: that id=None so that it can be re-coputed
    earlier_release = one_solver.copy(
        update={"version": f"{one_solver.version}beta"}, deep=True
    )
    assert earlier_release.pep404_version.is_prerelease
    assert earlier_release.pep404_version < one_solver.pep404_version

    # and yet a completely different solver
    another_solver = one_solver.copy(update={"id": "simcore/services/comp/zSolve"})
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
