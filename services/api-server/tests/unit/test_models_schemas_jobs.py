# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import random
import urllib.parse
from copy import deepcopy
from pprint import pformat
from uuid import uuid4

import pytest
from fastapi import FastAPI
from simcore_service_api_server._meta import api_vtag
from simcore_service_api_server.core.application import init_app
from simcore_service_api_server.models.schemas.jobs import (
    Job,
    JobInputs,
    JobOutputs,
    JobStatus,
)
from simcore_service_api_server.models.schemas.solvers import Solver


@pytest.mark.parametrize("model_cls", (Job, JobInputs, JobOutputs, JobStatus))
def test_jobs_model_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


def test_create_job_model():
    job = Job.create_now("solvers/isolve/releases/1.3.4", "12345")

    print(job.json())
    assert job.id is not None

    # TODO: https://stackoverflow.com/questions/5802108/how-to-check-if-a-datetime-object-is-localized-with-pytz/27596917
    # TODO: @validator("created_at", always=True)
    # def ensure_utc(cls, v):
    #    v.utc


@pytest.mark.parametrize("repeat", range(100))
def test_job_io_checksums(repeat):
    raw = {
        "values": {
            "x": 4.33,
            "n": 55,
            "title": "Temperature",
            "enabled": True,
            "input_file": {
                "filename": "input.txt",
                "id": "0a3b2c56-dbcd-4871-b93b-d454b7883f9f",
            },
        }
    }

    def _deepcopy_and_shuffle(src):
        if isinstance(src, dict):
            keys = list(src.keys())
            random.shuffle(keys)
            return {k: _deepcopy_and_shuffle(src[k]) for k in keys}
        return deepcopy(src)

    shuffled_raw = _deepcopy_and_shuffle(raw)
    inputs1 = JobInputs.parse_obj(raw)
    inputs2 = JobInputs.parse_obj(shuffled_raw)

    print(inputs1)
    print(inputs2)

    assert inputs1 == inputs2
    assert (
        inputs1.compute_checksum() == inputs2.compute_checksum()
    ), f"{inputs1}!={inputs2}"


@pytest.fixture
def app(project_env_devel_environment) -> FastAPI:
    _app: FastAPI = init_app()
    return _app


def test_job_resouce_names_has_associated_url(app: FastAPI):

    solver_key = "z43/name with spaces/isolve"
    solver_version = "1.0.3"
    job_id = uuid4()

    solver_name = Solver.compose_resource_name(solver_key, solver_version)
    job_name = Job.compose_resource_name(parent_name=solver_name, job_id=job_id)
    # job_name is used to identify a solver's job.

    # job_name is a RELATIVE resource name as defined in https://cloud.google.com/apis/design/resource_names
    #
    # - This a a relative resource name        "users/john smith/events/123"
    # - This is a calendar event resource name "//calendar.googleapis.com/users/john smith/events/123"
    # - This is the corresponding HTTP URL     "https://calendar.googleapis.com/v3/users/john%20smith/events/123"

    # let's make sure the associated url route is always defined in the route
    url_path = app.router.url_path_for(
        "get_job", solver_key=solver_key, version=solver_version, job_id=str(job_id)
    )

    assert url_path == f"/{api_vtag}/{urllib.parse.unquote_plus(job_name)}"
