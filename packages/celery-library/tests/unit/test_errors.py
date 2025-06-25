import pytest
from celery_library.errors import (
    decode_celery_transferrable_error,
    encode_celery_transferrable_error,
)
from models_library.api_schemas_storage.export_data_async_jobs import AccessRightError


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
        result = encode_celery_transferrable_error(e)

        assert decode_celery_transferrable_error(result).args == original_error.args
        assert f"{decode_celery_transferrable_error(result)}" == f"{original_error}"
        assert f"{result}" == f"{original_error}"
        assert result.args != original_error.args
