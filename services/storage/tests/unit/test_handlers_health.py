# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access


import simcore_service_storage._meta
from aiohttp.test_utils import TestClient
from models_library.api_schemas_storage import S3BucketName
from models_library.app_diagnostics import AppStatusCheck
from moto.server import ThreadedMotoServer
from pytest_simcore.helpers.assert_checks import assert_status
from servicelib.aiohttp import status
from simcore_service_storage.handlers_health import HealthCheck
from types_aiobotocore_s3 import S3Client

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


async def test_health_check(client: TestClient):
    assert client.app
    url = client.app.router["health_check"].url_for()
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data
    assert not error

    app_health = HealthCheck.model_validate(data)
    assert app_health.name == simcore_service_storage._meta.PROJECT_NAME  # noqa: SLF001
    assert app_health.version == str(
        simcore_service_storage._meta.VERSION
    )  # noqa: SLF001


async def test_health_status(client: TestClient):
    assert client.app
    url = client.app.router["get_status"].url_for()
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data
    assert not error

    app_status_check = AppStatusCheck.model_validate(data)
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
    client: TestClient,
    storage_s3_bucket: S3BucketName,
    s3_client: S3Client,
):
    assert client.app
    url = client.app.router["get_status"].url_for()
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data
    assert not error
    app_status_check = AppStatusCheck.model_validate(data)
    assert app_status_check.services["s3"]["healthy"] == "connected"
    # now delete the bucket
    await s3_client.delete_bucket(Bucket=storage_s3_bucket)
    # check again the health
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data
    assert not error
    app_status_check = AppStatusCheck.model_validate(data)
    assert app_status_check.services["s3"]["healthy"] == "no access to S3 bucket"


async def test_bad_health_status_if_s3_server_missing(
    client: TestClient, mocked_aws_server: ThreadedMotoServer
):
    assert client.app
    url = client.app.router["get_status"].url_for()
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data
    assert not error
    app_status_check = AppStatusCheck.model_validate(data)
    assert app_status_check.services["s3"]["healthy"] == "connected"
    # now disable the s3 server
    mocked_aws_server.stop()
    # check again the health
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data
    assert not error
    app_status_check = AppStatusCheck.model_validate(data)
    assert app_status_check.services["s3"]["healthy"] == "failed"
    # start the server again
    mocked_aws_server.start()
    # should be good again
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data
    assert not error
    app_status_check = AppStatusCheck.model_validate(data)
    assert app_status_check.services["s3"]["healthy"] == "connected"
