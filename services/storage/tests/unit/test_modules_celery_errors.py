import pytest
from models_library.api_schemas_storage.export_data_async_jobs import AccessRightError
from simcore_service_storage.modules.celery.errors import (
    decode_celery_transferrable_error,
    encore_celery_transferrable_error,
)


@pytest.mark.parametrize(
    "original_error",
    [
        RuntimeError("some error"),
        AccessRightError(user_id=1, file_id="a/path/to/a/file.txt", location_id=0),
    ],
)
def test_workflow(original_error: Exception):
    try:
        raise original_error  # noqa: TRY301
    except Exception as e:  # pylint: disable=broad-exception-caught
        result = encore_celery_transferrable_error(e)

        assert decode_celery_transferrable_error(result).args == original_error.args
        assert f"{decode_celery_transferrable_error(result)}" == f"{original_error}"
        assert f"{result}" == f"{original_error}"
        assert result.args != original_error.args
