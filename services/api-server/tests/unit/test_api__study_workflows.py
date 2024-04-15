# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import functools
import io
import json
import textwrap
import time
from contextlib import suppress
from pathlib import Path

import httpx
import pytest
from fastapi.encoders import jsonable_encoder
from pytest_simcore.helpers.utils_host import get_localhost_ip
from respx import MockRouter
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.pagination import OnePage
from simcore_service_api_server.models.schemas.errors import ErrorGet
from simcore_service_api_server.models.schemas.files import File
from simcore_service_api_server.models.schemas.jobs import Job, JobOutputs, JobStatus
from simcore_service_api_server.models.schemas.studies import StudyPort


def _handle_http_status_error(func):
    @functools.wraps(func)
    async def _handler(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)

        except httpx.HTTPStatusError as exc:
            msg = exc.response.text
            # rewrite exception's message
            with suppress(Exception), io.StringIO() as sio:
                print(exc, file=sio)
                for e in ErrorGet(**exc.response.json()).errors:
                    print("\t", e, file=sio)
                msg = sio.getvalue()

            raise httpx.HTTPStatusError(
                message=msg, request=exc.request, response=exc.response
            ) from exc

    return _handler


class _BaseTestApi:
    def __init__(
        self, client: httpx.AsyncClient, tmp_path: Path | None = None, **request_kwargs
    ):
        self._client = client
        self._request_kwargs = request_kwargs
        self._tmp_path = tmp_path


class FilesTestApi(_BaseTestApi):
    @_handle_http_status_error
    async def upload_file(self, path: Path) -> File:
        with path.open("rb") as fh:
            resp = await self._client.put(
                f"{API_VTAG}/files/content",
                files={"file": fh},
                **self._request_kwargs,
            )
        resp.raise_for_status()
        return File(**resp.json())

    @_handle_http_status_error
    async def download_file(self, file_id, suffix=".downloaded") -> Path:
        assert self._tmp_path
        path_to_save = self._tmp_path / f"{file_id}{suffix}"
        resp = await self._client.get(
            f"{API_VTAG}/files/{file_id}/content",
            follow_redirects=True,
            **self._request_kwargs,
        )
        resp.raise_for_status()
        path_to_save.write_bytes(resp.content)
        return path_to_save


class StudiesTestApi(_BaseTestApi):
    @_handle_http_status_error
    async def list_study_ports(self, study_id):
        resp = await self._client.get(
            f"/v0/studies/{study_id}/ports",
            **self._request_kwargs,
        )
        resp.raise_for_status()
        return OnePage[StudyPort](**resp.json())

    @_handle_http_status_error
    async def create_study_job(self, study_id, job_inputs: dict) -> Job:
        resp = await self._client.post(
            f"{API_VTAG}/studies/{study_id}/jobs",
            json=jsonable_encoder(job_inputs),
            **self._request_kwargs,
        )
        resp.raise_for_status()
        return Job(**resp.json())

    @_handle_http_status_error
    async def start_study_job(self, study_id, job_id) -> JobStatus:
        resp = await self._client.post(
            f"{API_VTAG}/studies/{study_id}/jobs/{job_id}:start",
            **self._request_kwargs,
        )
        resp.raise_for_status()
        return JobStatus(**resp.json())

    @_handle_http_status_error
    async def inspect_study_job(self, study_id, job_id) -> JobStatus:
        resp = await self._client.post(
            f"/v0/studies/{study_id}/jobs/{job_id}:inspect",
            **self._request_kwargs,
        )
        resp.raise_for_status()
        return JobStatus(**resp.json())

    @_handle_http_status_error
    async def get_study_job_outputs(self, study_id, job_id) -> JobOutputs:
        resp = await self._client.post(
            f"{API_VTAG}/studies/{study_id}/jobs/{job_id}/outputs",
            **self._request_kwargs,
        )
        resp.raise_for_status()
        return JobOutputs(**resp.json())

    @_handle_http_status_error
    async def delete_study_job(self, study_id, job_id) -> None:
        resp = await self._client.delete(
            f"{API_VTAG}/studies/{study_id}/jobs/{job_id}",
            **self._request_kwargs,
        )
        resp.raise_for_status()


@pytest.fixture
def input_json_path(tmp_path: Path) -> Path:
    # https://github.com/wvangeit/osparc-pyapi-tests/blob/master/noninter1/input.json
    p = tmp_path / "input.json"
    data = {"f1": 3}
    p.write_text(json.dumps(data))
    return p


@pytest.fixture
def input_data_path(tmp_path: Path) -> Path:
    p = tmp_path / "input.data"
    data = {"x1": 5.0, "y2": 7.5}
    p.write_text(json.dumps(data))
    return p


@pytest.fixture
def test_py_path(tmp_path: Path) -> Path:
    p = tmp_path / "test.py"
    code = textwrap.dedent(
        """\
    import os
    import json

    from pathlib import Path

    print("Konichiwa. O genki desu ka?")

    input_path = Path(os.environ["INPUT_FOLDER"])
    output_path = Path(os.environ["OUTPUT_FOLDER"])

    test_data_path = input_path / "input.data"

    test_data = json.loads(test_data_path.read_text())

    output_paths = {}
    for output_i in range(1, 6):
        output_paths[output_i] = output_path / f"output_{output_i}"

        output_paths[output_i].mkdir(parents=True, exist_ok=True)

    output_data_path = output_paths[1] / "output.data"

    output_data_path.write_text(json.dumps(test_data))

    print(f"Wrote output files to: {output_path.resolve()}")

    print("Genki desu")
    """
    )
    p.write_text(code)
    return p


# TODO: this is just to get mocks -------------------------
@pytest.fixture
async def client():
    async with httpx.AsyncClient(base_url=f"http://{get_localhost_ip()}:8006/") as cli:
        yield cli


@pytest.fixture
def auth():
    return httpx.BasicAuth("test", "test")


@pytest.fixture
def mocked_webserver_service_api_base() -> MockRouter | None:
    return None


# --------------------------------------------------


@pytest.mark.acceptance_test(
    "Reproduces https://github.com/wvangeit/osparc-pyapi-tests/blob/master/noninter1/run_study.py"
)
async def test_run_study_workflow(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    mocked_webserver_service_api_base: MockRouter,
    tmp_path: Path,
    input_json_path: Path,
    input_data_path: Path,
    test_py_path: Path,
):
    template_id = "aeab71fe-f71b-11ee-8fca-0242ac140008"

    files_api = FilesTestApi(client, tmp_path, auth=auth)
    studies_api = StudiesTestApi(client, auth=auth)

    # lists
    study_ports = await studies_api.list_study_ports(study_id=template_id)
    assert study_ports.total == 11
    # TODO: file-pickers are not considered ports  but can be set as inputs! This is inconsistent!
    # TODO: Expose Models in web-server.
    # TODO: file ports do not have schema !!
    # {
    #   "key": "0b8042c4-501a-4f9b-b2fa-17f860548b33",
    #   "kind": "output",
    #   "content_schema": null
    # },

    # uploads input files
    test_py_file: File = await files_api.upload_file(path=test_py_path)
    assert test_py_file.filename == test_py_path.name

    test_data_file: File = await files_api.upload_file(path=input_data_path)
    assert test_data_file.filename == input_data_path.name

    test_json_file: File = await files_api.upload_file(path=input_json_path)
    assert test_json_file.filename == input_json_path.name

    # creates job
    input_values = {
        "InputInt": 42,
        "InputString": "Z43",
        "InputArray": [1, 2, 3],
        "InputNumber": 3.14,
        "InputBool": False,
        "InputFile": test_json_file,
    }

    new_job: Job = await studies_api.create_study_job(
        study_id=template_id,
        job_inputs={"values": input_values},
    )

    # start & inspect job until done
    await studies_api.start_study_job(study_id=template_id, job_id=new_job.id)

    job_status: JobStatus = await studies_api.inspect_study_job(
        study_id=template_id, job_id=new_job.id
    )

    while job_status.state not in {"SUCCESS", "FAILED"}:
        job_status = await studies_api.inspect_study_job(
            study_id=template_id, job_id=new_job.id
        )
        print(f"Status: [{job_status.state}]")

        time.sleep(1)

    print(await studies_api.inspect_study_job(study_id=template_id, job_id=new_job.id))

    # get outputs
    job_outputs = await studies_api.get_study_job_outputs(
        study_id=template_id, job_id=new_job.id
    )

    print(job_outputs.results)

    assert job_outputs.results["OutputInt"] == input_values["InputInt"]
    assert job_outputs.results["OutputArray"] == input_values["InputArray"]
    assert job_outputs.results["OutputNumber"] == input_values["InputNumber"]

    output_filename = job_outputs.results["OutputFile"].filename
    output_file = Path(
        await files_api.download_file(
            job_outputs.results["OutputFile"].id, suffix=output_filename
        )
    )
    assert output_file.exists()
    assert json.loads(output_file.read_text()) == json.loads(
        input_json_path.read_text()
    )

    # deletes
    await studies_api.delete_study_job(study_id=template_id, job_id=new_job.id)
