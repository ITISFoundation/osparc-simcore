import pytest
from celery.exceptions import (  # type: ignore[import-untyped]
    BackendGetMetaError,
    CeleryError,
    OperationalError,
)
from celery_library.errors import (
    TaskManagerError,
    TaskOrGroupNotFoundError,
    decode_celery_transferable_error,
    encode_celery_transferable_error,
    handle_celery_errors,
)
from models_library.api_schemas_storage.export_data_async_jobs import AccessRightError
from redis.exceptions import ConnectionError as RedisConnectionError


@pytest.mark.parametrize(
    "original_error",
    [
        RuntimeError("some error"),
        AccessRightError(user_id=1, file_id="a/path/to/a/file.txt", location_id=0),
    ],
)
def test_error(original_error: Exception):
    try:
        raise original_error  # noqa: TRY301
    except Exception as e:  # pylint: disable=broad-exception-caught
        result = encode_celery_transferable_error(e)

        assert decode_celery_transferable_error(result).args == original_error.args
        assert f"{decode_celery_transferable_error(result)}" == f"{original_error}"
        assert f"{result}" == f"{original_error}"
        assert result.args != original_error.args


@pytest.mark.parametrize(
    "raised_error",
    [
        BackendGetMetaError(task_id="a-task"),
        CeleryError("celery is unhappy"),
        OperationalError("broker is unreachable"),
        RedisConnectionError("Connection reset by peer"),
    ],
)
async def test_handle_celery_errors_wraps_transport_errors(raised_error: Exception):
    @handle_celery_errors
    async def _raises() -> None:
        raise raised_error

    with pytest.raises(TaskManagerError):
        await _raises()


async def test_handle_celery_errors_lets_domain_errors_through():
    @handle_celery_errors
    async def _raises() -> None:
        raise TaskOrGroupNotFoundError(task_uuid="a-uuid", owner_metadata={})

    with pytest.raises(TaskOrGroupNotFoundError):
        await _raises()
