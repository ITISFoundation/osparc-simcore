# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from uuid import uuid4

import pytest
from simcore_service_api_server.api.routes.solvers_faker import SolversFaker
from simcore_service_api_server.models.schemas.solvers import (
    Job,
    JobInput,
    JobOutput,
    Solver,
    _compose_job_id,
)


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


@pytest.mark.parametrize("model_cls", (Job, Solver, JobInput, JobOutput))
def test_solvers_model_examples(model_cls):
    example = model_cls.Config.schema_extra["example"]
    print(example)

    model_instance = model_cls(**example)
    assert model_instance
