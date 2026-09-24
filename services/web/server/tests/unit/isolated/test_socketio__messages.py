# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
"""`_safe_emit` must never let a forged CancelledError escape.

The socket.io RabbitMQ manager raises asyncio.CancelledError from aio-pika's
ChannelInvalidStateError even though nobody cancelled (SEE
https://github.com/miguelgrinberg/python-socketio/commit/cd7f781c022dd1d1ec3c6695a0fd6ab3ce864fd5).
Letting it escape would abort strict callers (e.g. the outbox consumer) and even
get silently swallowed by gather(return_exceptions=True) collectors. `_safe_emit`
therefore translates it into a regular ConnectionError whenever the running task
was not actually cancelled, while a genuine cancellation keeps propagating.
"""

import asyncio

import pytest
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.socketio import SocketMessageDict
from simcore_service_webserver.socketio._messages import _safe_emit
from socketio import AsyncServer  # type: ignore[import-untyped]

_MESSAGE = SocketMessageDict(event_type="test:event", data={})
_ROOM = SocketIORoomStr.from_group_id(1)


async def _run_in_task(coro_factory) -> asyncio.Task:
    task = asyncio.create_task(coro_factory())
    await asyncio.sleep(0)  # let the task start
    return task


async def test_forged_cancelled_error_translated_to_connection_error():
    """CancelledError with no cancellation requested (cancelling() == 0) must surface
    as a ConnectionError, so strict callers retry and non-strict ones only log it."""

    async def _forging_emit(*_args, **_kwargs):
        raise asyncio.CancelledError

    sio = AsyncServer()
    sio.emit = _forging_emit  # type: ignore[method-assign]

    with pytest.raises(ConnectionError):
        await _safe_emit(
            sio,
            room=_ROOM,
            message=_MESSAGE,
            ignore_queue=False,
            strict=True,
        )
    # (the original CancelledError is preserved in the log_catch error report)


async def test_genuine_cancellation_propagates():
    """When the running task really is cancelled, the CancelledError must propagate
    unchanged (shutdown semantics), never be translated into a ConnectionError."""

    async def _self_cancelling_emit(*_args, **_kwargs):
        asyncio.current_task().cancel()  # like a real caller-driven cancellation
        await asyncio.sleep(3600)

    sio = AsyncServer()
    sio.emit = _self_cancelling_emit  # type: ignore[method-assign]

    task = await _run_in_task(
        lambda: _safe_emit(
            sio,
            room=_ROOM,
            message=_MESSAGE,
            ignore_queue=False,
            strict=True,
        )
    )
    await asyncio.sleep(0.1)  # let the emit cancel the task
    assert task.cancelled() or task.done()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_regular_error_respects_strict_flag():
    """Non-CancelledError errors keep the existing semantics: strict re-raises,
    non-strict only logs."""

    async def _failing_emit(*_args, **_kwargs):
        msg = "broker connection closed"
        raise ConnectionResetError(msg)

    sio = AsyncServer()
    sio.emit = _failing_emit  # type: ignore[method-assign]

    with pytest.raises(ConnectionResetError):
        await _safe_emit(
            sio,
            room=_ROOM,
            message=_MESSAGE,
            ignore_queue=False,
            strict=True,
        )

    # non-strict must swallow it
    await _safe_emit(
        sio,
        room=_ROOM,
        message=_MESSAGE,
        ignore_queue=False,
        strict=False,
    )
