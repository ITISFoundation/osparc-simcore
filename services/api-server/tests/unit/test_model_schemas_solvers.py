# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from operator import attrgetter
from pprint import pformat
from uuid import uuid4

import pytest
from simcore_service_api_server.api.routes.solvers_faker import SolversFaker
from simcore_service_api_server.models.schemas.solvers import (
    Job,
    JobInput,
    JobOutput,
    Solver,
    Version,
    _compose_job_id,
)


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
    job = Job.create_now(uuid4(), "12345")

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
    solver0 = Solver(**Solver.Config.schema_extra["example"])

    assert isinstance(solver0.pep404_version, Version)
    major, minor, micro = solver0.pep404_version.release
    solver0.version = f"{major}.{minor}.{micro}"

    # and a different version of the same
    # NOTE: that id=None so that it can be re-coputed
    solver1 = solver0.copy(
        update={"version": f"{solver0.version}beta", "id": None}, deep=True
    )
    assert solver1.pep404_version.is_prerelease
    assert solver1.pep404_version < solver0.pep404_version
    assert solver0.id != solver1.id, "changing vesion should automaticaly change id"

    # and yet a completely different solver
    other_solver = solver0.copy(
        update={"name": f"simcore/services/comp/{faker.name()}", "id": None}
    )
    assert (
        solver0.id != other_solver.id
    ), "changing vesion should automaticaly change id"

    # let's sort a list of solvers by name and then by version
    sorted_solvers = sorted(
        [solver0, other_solver, solver1], key=attrgetter("name", "pep404_version")
    )

    # dont' really know reference solver name so...
    if solver0.name < other_solver.name:
        assert sorted_solvers == [solver1, solver0, other_solver]
    else:
        assert sorted_solvers == [other_solver, solver1, solver0]
