# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import urllib
import urllib.parse
from pathlib import Path
from pprint import pprint
from typing import Iterator
from zipfile import ZipFile

import boto3
import httpx
import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from pydantic import AnyUrl, HttpUrl, parse_obj_as
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings
from starlette import status


@pytest.fixture
def bucket_name():
    return "test-bucket"


@pytest.fixture
def project_id(faker: Faker):
    return faker.uuid4()


@pytest.fixture
def node_id(faker: Faker):
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
        aws_secret_access_key="xxx",
        aws_access_key_id="xxx",
    )
    s3_client.create_bucket(Bucket=bucket_name)

    # uploads file
    # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html
    object_name = f"{project_id}/{node_id}/{log_zip_path.name}"
    s3_client.upload_file(f"{log_zip_path}", bucket_name, object_name)

    # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.generate_presigned_url
    presigned_url = s3_client.generate_presigned_url(
        ClientMethod=s3_client.get_object.__name__,
        Params={"Bucket": bucket_name, "Key": object_name},
        ExpiresIn=3600,  # secs
    )

    # SEE also https://gist.github.com/amarjandu/77a7d8e33623bae1e4e5ba40dc043cb9
    yield parse_obj_as(AnyUrl, presigned_url)


@pytest.fixture
def mocked_directorv2_service_api(
    app: FastAPI, faker: Faker, presigned_download_link: AnyUrl
):
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_DIRECTOR_V2

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_DIRECTOR_V2.base_url,
        assert_all_called=False,
        assert_all_mocked=False,
    ) as respx_mock:

        respx_mock.get(
            path__regex=r"/computations/(?P<project_id>[\w-]+)/tasks/-/logs",
            name="get_computation_logs",
        ).respond(
            status.HTTP_200_OK,
            json={"iSolve": presigned_download_link},
        )

        yield respx_mock


def test_download_presigned_link(
    presigned_download_link: AnyUrl, tmp_path: Path, project_id: str, node_id: str
):
    """Cheks that the generation of presigned_download_link works as expected"""
    r = httpx.get(presigned_download_link)
    pprint(dict(r.headers))
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
):
    resp = await client.get("/v0/meta")
    assert resp.status_code == 200

    solver_key = urllib.parse.quote_plus("simcore/services/comp/itis/isolve")
    version = "1.2.3"
    job_id = project_id

    resp = await client.get(
        f"/v0/solvers/{solver_key}/releases/{version}/jobs/{job_id}/outputs/logs",
        auth=auth,
        allow_redirects=True,
    )

    # calls to directorv2 service
    assert mocked_directorv2_service_api["get_computation_logs"].called

    # was a re-direction
    resp0 = resp.history[0]
    assert resp0.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert resp0.headers["location"] == presigned_download_link

    assert resp.url == presigned_download_link
    pprint(dict(resp.headers))

    assert resp.status_code == 200, resp.text
