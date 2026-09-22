# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Iterator

import celery_library.errors_adapters as errors_adapters_module
import httpx2
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
from celery_library.errors_adapters import register_transferable_error_adapter
from common_library.errors_classes import OsparcErrorMixin
from models_library.api_schemas_storage.export_data_async_jobs import AccessRightError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import DataError as RedisDataError
from redis.exceptions import TimeoutError as RedisTimeoutError


def _make_http_status_error() -> httpx2.HTTPStatusError:
    # NOTE: httpx.HTTPStatusError can be pickled (dumps succeeds) but cannot be
    # reconstructed by pickle.loads since __init__ requires keyword-only
    # `request`/`response` -- it used to crash the consumers of failed jobs
    return httpx2.HTTPStatusError(
        "Client error '404 Not Found'",
        request=httpx2.Request("GET", "http://fake-storage/v0/files"),
        response=httpx2.Response(404),
    )


class TransferableHTTPStatusError(OsparcErrorMixin, Exception):
    """Serializable wire error for httpx.HTTPStatusError (example adapter)."""

    msg_template = "{original_message}"

    original_message: str
    method: str
    url: str
    status_code: int
    reason_phrase: str

    # Adapters to/from

    @classmethod
    def from_http_status_error(cls, error: httpx2.HTTPStatusError) -> "TransferableHTTPStatusError":
        return cls(
            original_message=f"{error}",
            method=error.request.method,
            url=f"{error.request.url}",
            status_code=error.response.status_code,
            reason_phrase=error.response.reason_phrase,
        )

    def to_http_status_error(self) -> httpx2.HTTPStatusError:
        return httpx2.HTTPStatusError(
            self.original_message,
            request=httpx2.Request(self.method, self.url),
            # httpx derives reason_phrase from status_code (its __init__ does not
            # accept one), so the wire field is only kept for reporting
            response=httpx2.Response(self.status_code),
        )


@pytest.fixture
def registered_http_status_error_adapter() -> Iterator[None]:
    # the registry is process-global (workers and consumers register at startup);
    # snapshot and restore it so tests stay independent of ordering
    to_wire_snapshot = dict(errors_adapters_module.to_wire_adapters)
    from_wire_snapshot = dict(errors_adapters_module.from_wire_adapters)
    register_transferable_error_adapter(
        original_type=httpx2.HTTPStatusError,
        wire_type=TransferableHTTPStatusError,
        to_wire=TransferableHTTPStatusError.from_http_status_error,
        from_wire=TransferableHTTPStatusError.to_http_status_error,
    )
    yield
    errors_adapters_module.to_wire_adapters.clear()
    errors_adapters_module.to_wire_adapters.update(to_wire_snapshot)
    errors_adapters_module.from_wire_adapters.clear()
    errors_adapters_module.from_wire_adapters.update(from_wire_snapshot)


def test_adapter_round_trips_the_original_error(registered_http_status_error_adapter: None):
    # transform -> transmit -> untransform: the consumer gets a real HTTPStatusError back
    original_error = _make_http_status_error()

    result = encode_celery_transferable_error(original_error)
    decoded = decode_celery_transferable_error(result)

    assert isinstance(decoded, httpx2.HTTPStatusError)
    assert decoded.response.status_code == 404
    assert decoded.request.method == "GET"
    assert f"{decoded.request.url}" == "http://fake-storage/v0/files"
    assert f"{decoded}" == f"{original_error}"
    assert f"{result}" == f"{original_error}"


def test_wire_error_survives_without_consumer_adapter(registered_http_status_error_adapter: None):
    # worker registered the adapter but the consumer did not: decoding the payload
    # yields the wire error as-is, which is serializable and reportable
    original_error = _make_http_status_error()
    result = encode_celery_transferable_error(original_error)

    wire_snapshot = dict(errors_adapters_module.from_wire_adapters)
    errors_adapters_module.from_wire_adapters.clear()
    try:
        decoded = decode_celery_transferable_error(result)
    finally:
        errors_adapters_module.from_wire_adapters.update(wire_snapshot)

    assert isinstance(decoded, TransferableHTTPStatusError)
    assert decoded.status_code == 404
    assert f"{decoded}" == f"{original_error}"


def test_unregistered_error_keeps_the_old_behavior():
    original_error = _make_http_status_error()  # no adapter registered here

    result = encode_celery_transferable_error(original_error)
    decoded = decode_celery_transferable_error(result)

    # falls back to the stand-in path instead of raising
    assert type(decoded).__name__ == "HTTPStatusError"
    assert f"{decoded}" == f"{original_error}"


class _UnpicklableError(Exception):
    # cannot be pickled at all (e.g. broken __reduce__/__getstate__)
    def __reduce__(self):
        raise RuntimeError


class _BrokenStrUnpicklableError(_UnpicklableError):
    # neither picklable nor even stringifiable
    def __str__(self):
        raise RuntimeError


def test_unpicklable_error_transfers_a_text_description():
    original_error = _UnpicklableError("disk on fire")

    result = encode_celery_transferable_error(original_error)
    decoded = decode_celery_transferable_error(result)

    # the plain-text fallback keeps type name and message reportable
    assert type(decoded).__name__ == "_UnpicklableError"
    assert "disk on fire" in f"{decoded}"
    assert f"{result}" == f"{decoded}"


def test_unpicklable_error_with_broken_str_still_transfers():
    original_error = _BrokenStrUnpicklableError()

    result = encode_celery_transferable_error(original_error)  # must not raise
    decoded = decode_celery_transferable_error(result)

    assert type(decoded).__name__ == "_BrokenStrUnpicklableError"


@pytest.mark.parametrize(
    "original_error",
    [
        RuntimeError("some error"),
        AccessRightError(user_id=1, file_id="a/path/to/a/file.txt", location_id=0),
        # picklable but never unpicklable: without a registered adapter it must
        # still transfer through the stand-in path instead of raising
        _make_http_status_error(),
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
        RedisTimeoutError("Timeout reading from socket"),
    ],
)
async def test_handle_celery_errors_wraps_transport_errors(raised_error: Exception):
    @handle_celery_errors
    async def _raises() -> None:
        raise raised_error

    with pytest.raises(TaskManagerError):
        await _raises()


@pytest.mark.parametrize(
    "raised_error",
    [
        RedisDataError("invalid input"),
        TaskOrGroupNotFoundError(task_uuid="a-uuid", owner_metadata={}),
    ],
)
async def test_handle_celery_errors_lets_non_transient_errors_through(raised_error: Exception):
    @handle_celery_errors
    async def _raises() -> None:
        raise raised_error

    with pytest.raises(type(raised_error)):
        await _raises()
