# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import sys
import time
from datetime import timedelta
from pathlib import Path
from pprint import pformat
from typing import List

import httpx
import osparc
import packaging.version as pv
import pytest
from osparc.api.files_api import FilesApi
from osparc.configuration import Configuration
from osparc.models import FileMetadata, Job, JobStatus, Meta, Solver
from osparc.rest import ApiException

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def as_dict(obj: object):
    return {
        attr: getattr(obj, attr)
        for attr in obj.__dict__.keys()
        if not attr.startswith("_")
    }


# ----------


@pytest.fixture(scope="module")
def registered_user():
    user = {
        "email": "foo@mymail.com",
        "password": "my secret",
    }

    with httpx.Client(base_url="http://172.16.8.68:9081/v0") as client:
        # setup user via web-api
        resp = client.post(
            "/auth/login",
            json={
                "email": user["email"],
                "password": user["password"],
            },
        )

        if resp.status_code != 200:
            resp = client.post(
                "/auth/register",
                json={
                    "email": user["email"],
                    "password": user["password"],
                    "confirm": user["password"],
                    "invitation": "33c451d4-17b7-4e65-9880-694559b8ffc2",
                },
            )
            resp.raise_for_status()

        # create a key via web-api
        resp = client.post("/auth/api-keys", json={"display_name": "test-public-api"})

        print(resp.text)
        resp.raise_for_status()

        data = resp.json()["data"]
        assert data["display_name"] == "test-public-api"

        user.update({"api_key": data["api_key"], "api_secret": data["api_secret"]})

        yield user

        resp = client.request(
            "DELETE", "/auth/api-keys", json={"display_name": "test-public-api"}
        )


@pytest.fixture
def api_client(registered_user):
    cfg = Configuration(
        host=os.environ.get("OSPARC_API_URL", "http://127.0.0.1:8006"),
        username=registered_user["api_key"],
        password=registered_user["api_secret"],
    )
    print("cfg", pformat(as_dict(cfg)))

    with osparc.ApiClient(cfg) as api_client:
        yield api_client


@pytest.fixture()
def meta_api(api_client):
    return osparc.MetaApi(api_client)


@pytest.fixture()
def files_api(api_client):
    return osparc.FilesApi(api_client)


@pytest.fixture()
def solvers_api(api_client):
    return osparc.SolversApi(api_client)


@pytest.fixture()
def jobs_api(api_client):
    return osparc.JobsApi(api_client)


# ----------


def test_get_service_metadata(meta_api):
    print("get Service Metadata", "-" * 10)
    meta: Meta = meta_api.get_service_metadata()
    print(meta)
    assert isinstance(meta, Meta)

    meta, status_code, headers = meta_api.get_service_metadata_with_http_info()

    assert isinstance(meta, Meta)
    assert status_code == 200


def test_upload_file(files_api, tmpdir):
    input_path = Path(tmpdir) / "some-text-file.txt"
    input_path.write_text("demo")

    input_file: FileMetadata = files_api.upload_file(file=input_path)
    assert isinstance(input_file, FileMetadata)
    time.sleep(2)  # let time to upload to S3

    assert input_file.filename == input_path.name
    assert input_file.content_type == "text/plain"

    same_file = files_api.get_file(input_file.file_id)
    assert same_file == input_file

    same_file = files_api.upload_file(file=input_path)
    assert input_file.checksum == same_file.checksum


def test_upload_list_and_download(files_api: FilesApi, tmpdir):
    input_path = Path(tmpdir) / "some-hdf5-file.h5"
    input_path.write_bytes(b"demo but some other stuff as well")

    input_file: FileMetadata = files_api.upload_file(file=input_path)
    assert isinstance(input_file, FileMetadata)
    time.sleep(2)  # let time to upload to S3

    assert input_file.filename == input_path.name

    myfiles = files_api.list_files()
    assert myfiles
    assert all(isinstance(f, FileMetadata) for f in myfiles)
    assert input_file in myfiles

    same_file = files_api.download_file(file_id=input_file.file_id)
    assert input_path.read_text() == same_file


def test_solvers(solvers_api):
    solvers: List[Solver] = solvers_api.list_solvers()

    latest = None
    for solver in solvers:
        if "isolve" in solver.name:
            if not latest:
                latest = solver
            elif pv.parse(latest.version) < pv.parse(solver.version):
                latest = solvers_api.get_solver_by_id(solver.id)

    print(latest)
    assert latest

    assert (
        solvers_api.get_solver_by_name_and_version(
            solver_name=latest.name, version="latest"
        )
        == latest
    )
    assert solvers_api.get_solver(latest.id) == latest


def test_run_solvers(solvers_api, jobs_api):

    solver = solvers_api.get_solver_by_name_and_version(
        solver_name="simcore/services/comp/isolve", version="latest"
    )
    assert isinstance(solver, Solver)

    #
    # Why creating a job and not just running directly from solver?
    # Adding this intermediate step allows the server to do some extra checks before running a job.
    # For instance, does user has enough resources left? If not, the job could be rejected
    #

    # I would like to run a job with my solver and these inputs.
    # TODO: how to name the body so we get nice doc?
    job = solvers_api.create_job(solver.id, job_input=[])

    # Job granted. Resources reserved for you during N-minutes
    assert isinstance(job, Job)

    # TODO: change to uid
    assert job.id
    assert job == jobs_api.get_job(job.id)

    # gets jobs granted for user with a given solver
    solver_jobs = solvers_api.list_jobs(solver.id)
    assert job in solver_jobs

    # I only have jobs from this solver ?
    all_jobs = jobs_api.list_all_jobs()
    assert len(solver_jobs) <= len(all_jobs)
    assert all(job in all_jobs for job in solver_jobs)

    # let's run the job
    status = jobs_api.start_job(job.id)
    assert isinstance(status, JobStatus)

    assert status.state == "undefined"
    assert status.progress == 0
    assert (
        job.created_at < status.submitted_at < (job.created_at + timedelta(seconds=2))
    )

    # polling inspect_job
    while not status.stopped_at:
        time.sleep(0.5)
        status = jobs_api.inspect_job(job.id)
        print("Solver progress", f"{status.progress}/100", flush=True)

    # done
    assert status.progress == 100
    assert status.state in ["success", "failed"]
    assert status.submitted_at < status.started_at
    assert status.started_at < status.stopped_at

    # let's get the results
    try:
        outputs = jobs_api.list_job_outputs(job.id)
        for output in outputs:
            print(output)
            assert output.job_id == job.id
            assert output == jobs_api.get_job_output(job.id, output.name)

    except ApiException as err:
        assert (
            status.state == "failed" and err.status == 404
        ), f"No outputs if job failed {err}"
