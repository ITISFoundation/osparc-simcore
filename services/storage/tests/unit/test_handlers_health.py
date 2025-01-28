# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access


import httpx
import simcore_service_storage._meta
from fastapi import FastAPI
from models_library.api_schemas_storage import HealthCheck, S3BucketName
from models_library.app_diagnostics import AppStatusCheck
from moto.server import ThreadedMotoServer
from pytest_simcore.helpers.fastapi import assert_status
from pytest_simcore.helpers.httpx_assert_checks import url_from_operation_id
from servicelib.aiohttp import status
from types_aiobotocore_s3 import S3Client

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


async def test_health_check(initialized_app: FastAPI, client: httpx.AsyncClient):
    url = url_from_operation_id(client, initialized_app, "get_health")
    response = await client.get(f"{url}")
    app_health, error = assert_status(response, status.HTTP_200_OK, HealthCheck)
    assert app_health
    assert not error

    assert app_health.name == simcore_service_storage._meta.PROJECT_NAME  # noqa: SLF001
    assert app_health.version == str(
        simcore_service_storage._meta.VERSION
    )  # noqa: SLF001


async def test_health_status(initialized_app: FastAPI, client: httpx.AsyncClient):
    url = url_from_operation_id(client, initialized_app, "get_status")
    response = await client.get(f"{url}")
    app_status_check, error = assert_status(
        response, status.HTTP_200_OK, AppStatusCheck
    )
    assert app_status_check
    assert not error

    assert (
        app_status_check.app_name == simcore_service_storage._meta.PROJECT_NAME
    )  # noqa: SLF001
    assert app_status_check.version == str(
        simcore_service_storage._meta.VERSION
    )  # noqa: SLF001
    assert len(app_status_check.services) == 2
    assert "postgres" in app_status_check.services
    assert "healthy" in app_status_check.services["postgres"]
    assert app_status_check.services["postgres"]["healthy"] == "connected"
    assert "s3" in app_status_check.services
    assert "healthy" in app_status_check.services["s3"]
    assert app_status_check.services["s3"]["healthy"] == "connected"


async def test_bad_health_status_if_bucket_missing(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    storage_s3_bucket: S3BucketName,
    s3_client: S3Client,
):
    url = url_from_operation_id(client, initialized_app, "get_status")
    response = await client.get(f"{url}")
    app_status_check, error = assert_status(
        response, status.HTTP_200_OK, AppStatusCheck
    )
    assert app_status_check
    assert not error
    assert app_status_check.services["s3"]["healthy"] == "connected"
    # now delete the bucket
    await s3_client.delete_bucket(Bucket=storage_s3_bucket)
    # check again the health
    response = await client.get(f"{url}")
    app_status_check, error = assert_status(
        response, status.HTTP_200_OK, AppStatusCheck
    )
    assert app_status_check
    assert not error
    assert app_status_check.services["s3"]["healthy"] == "no access to S3 bucket"


async def test_bad_health_status_if_s3_server_missing(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    mocked_aws_server: ThreadedMotoServer,
):
    url = url_from_operation_id(client, initialized_app, "get_status")
    response = await client.get(f"{url}")
    app_status_check, error = assert_status(
        response, status.HTTP_200_OK, AppStatusCheck
    )
    assert app_status_check
    assert not error
    assert app_status_check.services["s3"]["healthy"] == "connected"
    # now disable the s3 server
    mocked_aws_server.stop()
    # check again the health
    response = await client.get(f"{url}")
    app_status_check, error = assert_status(
        response, status.HTTP_200_OK, AppStatusCheck
    )
    assert app_status_check
    assert not error
    assert app_status_check.services["s3"]["healthy"] == "failed"
    # start the server again
    mocked_aws_server.start()
    # should be good again
    response = await client.get(f"{url}")
    app_status_check, error = assert_status(
        response, status.HTTP_200_OK, AppStatusCheck
    )
    assert app_status_check
    assert not error
    assert app_status_check.services["s3"]["healthy"] == "connected"
