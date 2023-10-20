# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Iterator
from pathlib import Path
from pprint import pprint
from typing import Any
from unittest import mock
from zipfile import ZipFile

import arrow
import boto3
import httpx
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.services import ServiceDockerData
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl, HttpUrl, parse_obj_as
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.models.schemas.jobs import Job, JobInputs, JobStatus
from simcore_service_api_server.services.director_v2 import ComputationTaskGet
from starlette import status


@pytest.fixture
def bucket_name():
    return "test-bucket"


@pytest.fixture
def project_id(faker: Faker) -> str:
    return faker.uuid4()


@pytest.fixture
def node_id(faker: Faker) -> str:
    return faker.uuid4()


@pytest.fixture
def log_zip_path(faker: Faker, tmp_path: Path, project_id: str, node_id: str) -> Path:
    # a log file
    log_path = tmp_path / f"{project_id}-{node_id}.log"
    log_path.write_text(f"This is a log from {project_id}/{node_id}.\n{faker.text()}")

    # zipped
    zip_path = tmp_path / "log.zip"
    with ZipFile(zip_path, "w") as zf:
        zf.write(log_path)
    return zip_path


@pytest.fixture
def presigned_download_link(
    log_zip_path: Path,
    project_id: str,
    node_id: str,
    bucket_name: str,
    mocked_s3_server_url: HttpUrl,
) -> Iterator[AnyUrl]:
    s3_client = boto3.client(
        "s3",
        endpoint_url=mocked_s3_server_url,
        # Some fake auth, otherwise botocore.exceptions.NoCredentialsError: Unable to locate credentials
        aws_secret_access_key="xxx",  # noqa: S106
        aws_access_key_id="xxx",
    )
    s3_client.create_bucket(Bucket=bucket_name)

    # uploads file
    # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html
    object_name = f"{project_id}/{node_id}/{log_zip_path.name}"
    s3_client.upload_file(f"{log_zip_path}", bucket_name, object_name)
    print("uploaded", object_name)

    # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.generate_presigned_url
    presigned_url = s3_client.generate_presigned_url(
        ClientMethod=s3_client.get_object.__name__,
        Params={"Bucket": bucket_name, "Key": object_name},
        ExpiresIn=3600,  # secs
    )
    print("generated link", presigned_url)

    # SEE also https://gist.github.com/amarjandu/77a7d8e33623bae1e4e5ba40dc043cb9
    return parse_obj_as(AnyUrl, presigned_url)


@pytest.fixture
def mocked_directorv2_service_api(
    app: FastAPI,
    presigned_download_link: AnyUrl,
    mocked_directorv2_service_api_base: MockRouter,
    directorv2_service_openapi_specs: dict[str, Any],
):
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_DIRECTOR_V2
    oas = directorv2_service_openapi_specs

    # pylint: disable=not-context-manager
    respx_mock = mocked_directorv2_service_api_base
    # check that what we emulate, actually still exists
    path = "/v2/computations/{project_id}/tasks/-/logfile"
    assert path in oas["paths"]
    assert "get" in oas["paths"][path]

    response = oas["paths"][path]["get"]["responses"]["200"]

    assert response["content"]["application/json"]["schema"]["type"] == "array"
    assert (
        response["content"]["application/json"]["schema"]["items"]["$ref"]
        == "#/components/schemas/TaskLogFileGet"
    )
    assert {"task_id", "download_link"} == set(
        oas["components"]["schemas"]["TaskLogFileGet"]["properties"].keys()
    )

    respx_mock.get(
        path__regex=r"/computations/(?P<project_id>[\w-]+)/tasks/-/logfile",
        name="get_computation_logs",  # = operation_id
    ).respond(
        status.HTTP_200_OK,
        json=[
            {
                "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "download_link": presigned_download_link,
            }
        ],
    )

    return respx_mock


def test_download_presigned_link(
    presigned_download_link: AnyUrl, tmp_path: Path, project_id: str, node_id: str
):
    """Cheks that the generation of presigned_download_link works as expected"""
    r = httpx.get(presigned_download_link)
    ## pprint(dict(r.headers))
    # r.headers looks like:
    # {
    #  'access-control-allow-origin': '*',
    #  'connection': 'close',
    #  'content-length': '491',
    #  'content-md5': 'HoY5Kfgqb9VSdS44CYBxnA==',
    #  'content-type': 'binary/octet-stream',
    #  'date': 'Thu, 19 May 2022 22:16:48 GMT',
    #  'etag': '"1e863929f82a6fd552752e380980719c"',
    #  'last-modified': 'Thu, 19 May 2022 22:16:48 GMT',
    #  'server': 'Werkzeug/2.1.2 Python/3.9.12',
    #  'x-amz-version-id': 'null',
    #  'x-amzn-requestid': 'WMAPXWFR2G4EJRVYBNJDRHTCXJ7NBRMDN7QQNHTQ5RYAQ34ZZNAL'
    # }
    assert r.status_code == status.HTTP_200_OK

    expected_fname = f"{project_id}-{node_id}.log"

    downloaded_path = tmp_path / "test_download_presigned_link.zip"
    downloaded_path.write_bytes(r.content)

    extract_dir = tmp_path / "extracted"
    extract_dir.mkdir()

    with ZipFile(f"{downloaded_path}") as fzip:
        assert any(Path(f).name == expected_fname for f in fzip.namelist())
        fzip.extractall(f"{extract_dir}")

    f = next(extract_dir.rglob(f"*{expected_fname}"))
    assert f"This is a log from {project_id}/{node_id}" in f.read_text()


async def test_solver_logs(
    client: httpx.AsyncClient,
    mocked_directorv2_service_api: MockRouter,
    auth: httpx.BasicAuth,
    project_id: str,
    presigned_download_link: AnyUrl,
    solver_key: str,
    solver_version: str,
):
    resp = await client.get("/v0/meta")
    assert resp.status_code == 200

    job_id = project_id

    resp = await client.get(
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs/{job_id}/outputs/logfile",
        auth=auth,
        follow_redirects=True,
    )

    # calls to directorv2 service
    assert mocked_directorv2_service_api["get_computation_logs"].called

    # was a re-direction
    resp0 = resp.history[0]
    assert resp0.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert resp0.headers["location"] == presigned_download_link

    assert resp.url == presigned_download_link
    pprint(dict(resp.headers))  # noqa: T203


@pytest.mark.acceptance_test(
    "New feature https://github.com/ITISFoundation/osparc-simcore/issues/3940"
)
async def test_run_solver_job(
    client: httpx.AsyncClient,
    directorv2_service_openapi_specs: dict[str, Any],
    catalog_service_openapi_specs: dict[str, Any],
    mocked_catalog_service_api: MockRouter,
    mocked_directorv2_service_api: MockRouter,
    mocked_webserver_service_api: MockRouter,
    auth: httpx.BasicAuth,
    project_id: str,
    solver_key: str,
    solver_version: str,
    mocked_groups_extra_properties: mock.Mock,
):
    oas = directorv2_service_openapi_specs

    # check that what we emulate, actually still exists
    path = "/v2/computations"
    assert path in oas["paths"]
    assert "post" in oas["paths"][path]

    response = oas["paths"][path]["post"]["responses"]["201"]

    assert (
        response["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ComputationGet"
    )
    assert {
        "id",
        "state",
        "result",
        "pipeline_details",
        "iteration",
        "cluster_id",
        "url",
        "stop_url",
        "submitted",
        "started",
        "stopped",
    } == set(oas["components"]["schemas"]["ComputationGet"]["properties"].keys())

    # CREATE and optionally start
    mocked_directorv2_service_api.post(
        path__regex=r"/computations",
        name="create_computation_v2_computations_post",
    ).respond(
        status.HTTP_201_CREATED,
        json=jsonable_encoder(
            ComputationTaskGet.parse_obj(
                {
                    "id": project_id,
                    "state": "UNKNOWN",
                    "result": "string",
                    "pipeline_details": {
                        "adjacency_list": {
                            "3fa85f64-5717-4562-b3fc-2c963f66afa6": [
                                "3fa85f64-5717-4562-b3fc-2c963f66afa6"
                            ],
                        },
                        "node_states": {
                            "3fa85f64-5717-4562-b3fc-2c963f66afa6": {
                                "modified": True,
                                "dependencies": [
                                    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
                                ],
                                "currentStatus": "NOT_STARTED",
                            },
                        },
                        "progress": 0.0,
                    },
                    "iteration": 1,
                    "cluster_id": 0,
                    "url": "http://test.com",
                    "stop_url": "http://test.com",
                    "started": None,
                    "stopped": None,
                    "submitted": arrow.utcnow().datetime.isoformat(),
                }
            )
        ),
    )

    # catalog_client.get_solver
    oas = catalog_service_openapi_specs
    response = oas["paths"]["/v0/services/{service_key}/{service_version}"]["get"][
        "responses"
    ]["200"]

    assert (
        response["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ServiceGet"
    )

    assert {
        "name",
        "description",
        "key",
        "version",
        "type",
        "authors",
        "contact",
        "inputs",
        "outputs",
    } == set(oas["components"]["schemas"]["ServiceGet"]["required"])

    example = next(
        e
        for e in ServiceDockerData.Config.schema_extra["examples"][::-1]
        if "boot" in e["description"]
    )

    mocked_catalog_service_api.get(
        # path__regex=r"/services/(?P<service_key>[\w-]+)/(?P<service_version>[0-9\.]+)",
        path=f"/v0/services/{solver_key}/{solver_version}",
        name="get_service_v0_services__service_key___service_version__get",
    ).respond(
        status.HTTP_200_OK,
        json=example
        | {
            "name": solver_key.split("/")[-1].capitalize(),
            "description": solver_key.replace("/", " "),
            "key": solver_key,
            "version": solver_version,
            "type": "computational",
        },
    )

    # ---------------------------------------------------------------------------------------------------------

    resp = await client.get("/v0/meta")
    assert resp.status_code == 200

    # Create Job
    resp = await client.post(
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs",
        auth=auth,
        json=JobInputs(
            values={
                "x": 3.14,
                "n": 42,
                # Tests https://github.com/ITISFoundation/osparc-issues/issues/948
                "a_list": [1, 2, 3],
            }
        ).dict(),
    )
    assert resp.status_code == status.HTTP_201_CREATED

    assert mocked_webserver_service_api["create_projects"].called
    assert mocked_webserver_service_api["get_task_status"].called
    assert mocked_webserver_service_api["get_task_result"].called

    job = Job.parse_obj(resp.json())

    # Start Job
    resp = await client.post(
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs/{job.id}:start",
        auth=auth,
        params={"cluster_id": 1},
    )
    assert resp.status_code == status.HTTP_200_OK
    assert mocked_directorv2_service_api[
        "create_computation_v2_computations_post"
    ].called

    job_status = JobStatus.parse_obj(resp.json())
    assert job_status.progress == 0.0
    mocked_groups_extra_properties.assert_called_once()
