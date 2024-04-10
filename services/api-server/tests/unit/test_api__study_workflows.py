# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
import time
from pathlib import Path

import httpx
import pytest
from attr import dataclass
from models_library.generated_models.docker_rest_api import File, JobStatus
from respx import MockRouter
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.jobs import Job, JobOutputs


@dataclass(frozen=True)
class _BaseApi:
    _client: httpx.AsyncClient
    _auth: httpx.BasicAuth
    _tmp_path: Path | None = None


class FilesApi(_BaseApi):
    async def upload_file(self, file: Path) -> File:
        resp: httpx.Response = await self._client.put(
            f"{API_VTAG}/files/content",
            files={"upload-file": file.open("rb")},
            auth=self._auth,
        )
        resp.raise_for_status()
        return File(**resp.json())

    async def download_file(self, file_id, suffix=".downloaded") -> Path:
        assert self._tmp_path

        path_to_save = self._tmp_path / f"{file_id}{suffix}"

        async with self._client.stream(
            "GET", f"{API_VTAG}/files/{file_id}/content"
        ) as resp:
            resp.raise_for_status()
            with path_to_save.open("wb") as file:
                async for chunk in resp.aiter_bytes():
                    file.write(chunk)

        return path_to_save


class StudiesApi(_BaseApi):
    async def list_study_ports(self, study_id):
        ...

    async def create_study_job(self, study_id, job_inputs: dict) -> Job:
        resp: httpx.Response = await self._client.post(
            f"{API_VTAG}/studies/{study_id}/jobs", json=job_inputs, auth=self._auth
        )
        resp.raise_for_status()
        return Job(**resp.json())

    async def start_study_job(self, study_id, job_id) -> JobStatus:
        raise NotImplementedError

    async def inspect_study_job(self, study_id, job_id) -> JobStatus:
        raise NotImplementedError

    async def get_study_job_outputs(self, study_id, job_id) -> JobOutputs:
        raise NotImplementedError


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
    code = r"""\
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
    p.write_text(code)
    return p


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
    template_id = "5b01fb90-f59f-11ee-9635-02420a140047"

    files_api = FilesApi(client, auth, tmp_path)
    studies_api = StudiesApi(client, auth)

    print(studies_api.list_study_ports(study_id=template_id))

    test_py_file = await files_api.upload_file(file=test_py_path)
    assert test_py_file

    test_data_file = await files_api.upload_file(file=input_data_path)
    assert test_data_file

    test_json_file = await files_api.upload_file(file=input_json_path)

    new_job = await studies_api.create_study_job(
        study_id=template_id,
        job_inputs={
            "values": {
                # "InputNumber1": 0.5,
                # "InputInteger1": 6,
                "InputFile1": test_json_file,
            }
        },
    )

    await studies_api.start_study_job(study_id=template_id, job_id=new_job.id)

    job_status = await studies_api.inspect_study_job(
        study_id=template_id, job_id=new_job.id
    )

    while job_status.state not in {"SUCCESS", "FAILED"}:
        job_status = await studies_api.inspect_study_job(
            study_id=template_id, job_id=new_job.id
        )
        print(f"Status: [{job_status.state}]")

        time.sleep(1)

    print(await studies_api.inspect_study_job(study_id=template_id, job_id=new_job.id))

    job_results = await studies_api.get_study_job_outputs(
        study_id=template_id, job_id=new_job.id
    ).results

    print(job_results)

    output_filename = job_results["OutputFile1"].filename
    output_file = Path(
        await files_api.download_file(
            job_results["OutputFile1"].id, suffix=output_filename
        )
    )
    assert output_file.exists()
