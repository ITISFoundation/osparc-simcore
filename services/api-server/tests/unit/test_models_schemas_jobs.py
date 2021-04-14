import random
from copy import deepcopy

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from pprint import pformat

import pytest
from simcore_service_api_server.models.schemas.jobs import (
    Job,
    JobInputs,
    JobOutputs,
    JobStatus,
)


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
