# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import functools
import inspect
import shutil
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from inspect import FullArgSpec
from pathlib import Path
from typing import Annotated, Any, Final
from unittest.mock import AsyncMock

import pytest
from annotated_types import doc
from async_asgi_testclient import TestClient
from faker import Faker
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from models_library.services import ServiceRunID
from pydantic import PositiveFloat
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from servicelib.logging_utils import LogLevelInt, LogMessageStr
from simcore_sdk.node_ports_common.exceptions import S3TransferError
from simcore_sdk.node_ports_common.file_io_utils import LogRedirectCB
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.modules.mounted_fs import MountedVolumes
from simcore_service_dynamic_sidecar.modules.notifications._notifications_ports import (
    PortNotifier,
)
from simcore_service_dynamic_sidecar.modules.outputs import _content_monitor as monitor_module
from simcore_service_dynamic_sidecar.modules.outputs import configure_outputs
from simcore_service_dynamic_sidecar.modules.outputs._content_monitor import _ScanResult
from simcore_service_dynamic_sidecar.modules.outputs._context import (
    OutputsContext,
    configure_outputs_context,
)
from simcore_service_dynamic_sidecar.modules.outputs._manager import (
    OutputsManager,
    UploadPortsFailedError,
    _PortKeyTracker,
    configure_outputs_manager,
)
from simcore_service_dynamic_sidecar.modules.outputs._upload_trust import PortUploadTrust
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

_SHORT_QUIET: Final[
    Annotated[timedelta, doc("quiet period for event-driven tests, replacing the production delay")]
] = timedelta(seconds=0.5)
_SHORT_QUIET_S: Final[PositiveFloat] = _SHORT_QUIET.total_seconds()
_SHORT_SWEEP: Final[Annotated[timedelta, doc("sweep interval for tests, replacing the production interval")]] = (
    timedelta(seconds=0.2)
)
_SHORT_SWEEP_S: Final[PositiveFloat] = _SHORT_SWEEP.total_seconds()
_SLEEP_PAST_SWEEPS_S: Final[Annotated[PositiveFloat, doc("wait spanning several short sweep intervals")]] = (
    _SHORT_SWEEP_S * 5
)
_TENACITY_POLL_UPLOADS: Final[dict[str, Any]] = {
    "reraise": True,
    "retry": retry_if_exception_type(AssertionError),
    "wait": wait_fixed(0.05),
    "stop": stop_after_delay(20),
}


@dataclass
class _MockError:
    error_class: type[BaseException]
    message: str


@dataclass
class ToggleErrorRaising:
    mock: AsyncMock
    successful_port_keys: list[str] = field(default_factory=list)
    _raise_errors: bool = True

    def stop_raising_errors(self) -> None:
        self._raise_errors = False


def test_configure_outputs_preserves_lifespan_order(mocker: MockerFixture):
    app_lifespan: LifespanManager[FastAPI] = LifespanManager()
    configured_lifespans: list[str] = []
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs.configure_outputs_manager",
        side_effect=lambda _: configured_lifespans.append("manager"),
    )
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs.configure_outputs_context",
        side_effect=lambda _: configured_lifespans.append("context"),
    )
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs.configure_outputs_watcher",
        side_effect=lambda _: configured_lifespans.append("watcher"),
    )

    configure_outputs(app_lifespan)

    assert configured_lifespans == ["context", "manager", "watcher"]


# FIXTURES


@pytest.fixture
def with_short_quiet(mocker: MockerFixture) -> None:
    """short quiet period so event-driven tests do not wait for the production delay"""
    mocker.patch.object(monitor_module, "_QUIET_SECONDS", _SHORT_QUIET_S)


@pytest.fixture
def with_short_sweep(mocker: MockerFixture) -> None:
    """short sweep period: request before outputs_manager so it applies to the first sweep"""
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs._manager._SWEEP_INTERVAL_S",
        _SHORT_SWEEP_S,
    )


@pytest.fixture(params=[0.01])
def upload_duration(request: pytest.FixtureRequest) -> PositiveFloat:
    return request.param


@pytest.fixture
def mock_upload_outputs(mocker: MockerFixture, upload_duration: PositiveFloat) -> Iterator[AsyncMock]:
    async def _mock_upload_outputs(*args, **kwargs) -> None:
        await asyncio.sleep(upload_duration)

    return mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs._manager.upload_outputs",
        side_effect=_mock_upload_outputs,
    )


@pytest.fixture(
    params=[
        _MockError(error_class=RuntimeError, message="mocked_nodeports_raised_error"),
        _MockError(error_class=S3TransferError, message="mocked_s3transfererror"),
    ]
)
def mock_error(request: pytest.FixtureRequest) -> _MockError:
    return request.param


@pytest.fixture
def mock_upload_outputs_raises_error(
    mocker: MockerFixture, mock_error: _MockError, upload_duration: PositiveFloat
) -> ToggleErrorRaising:
    async def _mock_upload_outputs(*args, **kwargs) -> None:
        if error_toggle._raise_errors:  # noqa: SLF001
            raise mock_error.error_class(mock_error.message)

        error_toggle.successful_port_keys.extend(kwargs["port_keys"])
        await asyncio.sleep(upload_duration)

    mock = mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs._manager.upload_outputs",
        side_effect=_mock_upload_outputs,
    )
    error_toggle = ToggleErrorRaising(mock=mock)

    return error_toggle


@pytest.fixture(params=[1, 4, 10])
def port_keys(request: pytest.FixtureRequest) -> list[str]:
    return [f"port_{i}" for i in range(request.param)]


@pytest.fixture
def outputs_path(tmp_path: Path) -> Path:
    return tmp_path


def _uploaded_port_keys(mock: AsyncMock) -> list[str]:
    uploaded: list[str] = []
    for call_args in mock.call_args_list:
        uploaded.extend(call_args.kwargs["port_keys"])
    return uploaded


def _assert_ports_uploaded(
    mock_upload_outputs: AsyncMock,
    port_keys: list[str],
    non_file_type_port_keys: list[str],
) -> None:
    uploaded_port_keys = _uploaded_port_keys(mock_upload_outputs)
    assert len(mock_upload_outputs.call_args_list) > 0
    assert set(uploaded_port_keys) == set(port_keys) | set(non_file_type_port_keys)


@pytest.fixture
def port_key_tracker() -> _PortKeyTracker:
    return _PortKeyTracker()


@pytest.fixture
async def port_key_tracker_with_ports(port_key_tracker: _PortKeyTracker, port_keys: list[str]) -> _PortKeyTracker:
    for port_key in port_keys:
        await port_key_tracker.add_pending(port_key)
    return port_key_tracker


@pytest.fixture(
    params=(
        [],
        ["non_file_port_1", "non_file_port_2"],
    )
)
def non_file_type_port_keys(request) -> list[str]:
    return request.param


@pytest.fixture
async def outputs_context(
    outputs_path: Path, port_keys: list[str], non_file_type_port_keys: list[str]
) -> OutputsContext:
    outputs_context = OutputsContext(outputs_path=outputs_path)
    await outputs_context.set_file_type_port_keys(port_keys)
    outputs_context.non_file_type_port_keys = non_file_type_port_keys
    return outputs_context


@pytest.fixture
async def outputs_manager(
    outputs_context: OutputsContext, port_notifier: PortNotifier, with_short_quiet: None
) -> AsyncIterator[OutputsManager]:
    outputs_manager = OutputsManager(
        outputs_context=outputs_context,
        port_notifier=port_notifier,
        io_log_redirect_cb=None,
        task_monitor_interval_s=0.01,
        progress_cb=None,
        background_uploads_enabled=True,
    )
    await outputs_manager.start()
    yield outputs_manager
    await outputs_manager.shutdown()


async def test_upload_port_wait_sequential(
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    non_file_type_port_keys: list[str],
    outputs_path: Path,
):
    for port_key in port_keys:
        await outputs_manager.port_key_content_changed(port_key=port_key)

    assert await outputs_manager._port_key_tracker.no_tracked_ports() is False  # noqa: SLF001
    await outputs_manager.wait_for_all_uploads_to_finish()
    assert await outputs_manager._port_key_tracker.no_tracked_ports() is True  # noqa: SLF001

    _assert_ports_uploaded(mock_upload_outputs, port_keys, non_file_type_port_keys)


async def test_upload_port_wait_parallel_parallel(
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    non_file_type_port_keys: list[str],
    outputs_path: Path,
):
    upload_tasks = [outputs_manager.port_key_content_changed(port_key=port_key) for port_key in port_keys]

    await asyncio.gather(*upload_tasks)
    await outputs_manager.wait_for_all_uploads_to_finish()

    _assert_ports_uploaded(mock_upload_outputs, port_keys, non_file_type_port_keys)


async def test_recovers_after_raising_error(
    mock_upload_outputs_raises_error: ToggleErrorRaising,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    non_file_type_port_keys: list[str],
    mock_error: _MockError,
):
    # expect to raise error the first time uploading
    for port_key in port_keys:
        await outputs_manager.port_key_content_changed(port_key)
        assert await outputs_manager._port_key_tracker.no_tracked_ports() is False  # noqa: SLF001
        await asyncio.sleep(outputs_manager.task_monitor_interval_s * 10)

    with pytest.raises(UploadPortsFailedError) as exec_info:
        await outputs_manager.wait_for_all_uploads_to_finish()

    failures = exec_info.value.failures  # pyright: ignore[reportAttributeAccessIssue]
    assert set(failures.keys()) == set(port_keys) | set(non_file_type_port_keys)

    def _assert_same_exceptions(first: list[str | None], second: list[type[BaseException]]) -> None:
        for formatted_traceback, error_class in zip(first, second, strict=True):
            assert formatted_traceback is not None
            assert error_class.__name__ in formatted_traceback
            assert mock_error.message in formatted_traceback

    _assert_same_exceptions(
        list(failures.values()),
        [mock_error.error_class] * len(failures),
    )

    # the second time uploading there is no error to be raised
    mock_upload_outputs_raises_error.stop_raising_errors()
    for port_key in port_keys:
        await outputs_manager.port_key_content_changed(port_key)
        assert await outputs_manager._port_key_tracker.no_tracked_ports() is False  # noqa: SLF001
        await asyncio.sleep(outputs_manager.task_monitor_interval_s * 10)

    await outputs_manager.wait_for_all_uploads_to_finish()


@pytest.fixture
async def single_port_manager(
    tmp_path: Path, port_notifier: PortNotifier, with_short_quiet: None
) -> AsyncIterator[tuple[OutputsManager, Path]]:
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    outputs_context = OutputsContext(outputs_path=outputs_dir)
    await outputs_context.set_file_type_port_keys(["output_1"])
    outputs_manager = OutputsManager(
        outputs_context=outputs_context,
        port_notifier=port_notifier,
        io_log_redirect_cb=None,
        task_monitor_interval_s=0.01,
        progress_cb=None,
        background_uploads_enabled=True,
    )
    await outputs_manager.start()
    yield outputs_manager, outputs_dir / "output_1"
    await outputs_manager.shutdown()


@dataclass
class PausableUpload:
    started: asyncio.Event
    release: asyncio.Event
    calls: list[list[str]] = field(default_factory=list)


@pytest.fixture
async def pausable_upload(mocker: MockerFixture) -> PausableUpload:
    pausable = PausableUpload(started=asyncio.Event(), release=asyncio.Event())

    async def _mock_upload_outputs(*args: Any, **kwargs: Any) -> None:
        pausable.calls.append(kwargs["port_keys"])
        pausable.started.set()
        await pausable.release.wait()

    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs._manager.upload_outputs",
        side_effect=_mock_upload_outputs,
    )
    return pausable


def _write_port_content(port_dir: Path, data: bytes) -> None:
    port_dir.mkdir(exist_ok=True)
    (port_dir / "f.dat").write_bytes(data)


async def test_event_uploads_only_after_the_quiet_period(
    pausable_upload: PausableUpload,
    single_port_manager: tuple[OutputsManager, Path],
):
    outputs_manager, port_dir = single_port_manager
    _write_port_content(port_dir, b"v1")

    outputs_manager.on_port_key_change("output_1")
    await asyncio.sleep(_SHORT_QUIET_S * 0.1)
    assert pausable_upload.calls == []  # quiet not elapsed yet

    await asyncio.wait_for(pausable_upload.started.wait(), timeout=10)
    pausable_upload.release.set()

    await outputs_manager.wait_for_all_uploads_to_finish()
    assert pausable_upload.calls.count(["output_1"]) == 1


async def test_late_events_postpone_the_upload(
    pausable_upload: PausableUpload,
    single_port_manager: tuple[OutputsManager, Path],
):
    outputs_manager, port_dir = single_port_manager
    _write_port_content(port_dir, b"v1")
    outputs_manager.on_port_key_change("output_1")

    await asyncio.sleep(_SHORT_QUIET_S * 0.4)
    _write_port_content(port_dir, b"v2")
    outputs_manager.on_port_key_change("output_1")  # timer restarts, nothing uploaded yet

    await asyncio.sleep(_SHORT_QUIET_S * 0.4)
    assert pausable_upload.calls == []

    await asyncio.wait_for(pausable_upload.started.wait(), timeout=10)
    pausable_upload.release.set()
    await outputs_manager.wait_for_all_uploads_to_finish()
    assert pausable_upload.calls.count(["output_1"]) == 1


async def test_upload_of_all_the_burst_content_happens_once_content_stops_changing(
    mock_upload_outputs: AsyncMock,
    single_port_manager: tuple[OutputsManager, Path],
):
    outputs_manager, port_dir = single_port_manager
    _write_port_content(port_dir, b"start")

    for counter in range(20):
        (port_dir / "f.dat").write_bytes(b"chunk-" * counter)
        outputs_manager.on_port_key_change("output_1")
        await asyncio.sleep(_SHORT_QUIET_S * 0.05)

    # the quiet period has not elapsed since the last write: nothing uploaded yet
    assert "output_1" not in _uploaded_port_keys(mock_upload_outputs)

    # a save runs its checks immediately and uploads the disk state as it is when the save runs
    await outputs_manager.wait_for_all_uploads_to_finish()
    assert _uploaded_port_keys(mock_upload_outputs).count("output_1") == 1


async def test_unchanged_content_is_not_uploaded_again(
    pausable_upload: PausableUpload,
    single_port_manager: tuple[OutputsManager, Path],
):
    outputs_manager, port_dir = single_port_manager
    _write_port_content(port_dir, b"v1")
    outputs_manager.on_port_key_change("output_1")

    await asyncio.wait_for(pausable_upload.started.wait(), timeout=10)
    pausable_upload.release.set()
    await outputs_manager.wait_for_all_uploads_to_finish()
    assert pausable_upload.calls.count(["output_1"]) == 1

    # an event without a content change: the check proves equality and skips
    outputs_manager.on_port_key_change("output_1")
    await asyncio.sleep(_SHORT_QUIET_S * 3)
    assert pausable_upload.calls.count(["output_1"]) == 1

    _write_port_content(port_dir, b"a longer v2")
    outputs_manager.on_port_key_change("output_1")
    await asyncio.wait_for(pausable_upload.started.wait(), timeout=10)
    pausable_upload.release.set()
    await outputs_manager.wait_for_all_uploads_to_finish()
    assert pausable_upload.calls.count(["output_1"]) == 2


async def test_failed_upload_is_retried_by_the_safety_sweep(
    with_short_sweep: None,
    mock_upload_outputs_raises_error: ToggleErrorRaising,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    outputs_path: Path,
):
    port_key = port_keys[0]
    for key in port_keys:
        port_dir = outputs_path / key
        port_dir.mkdir()
        (port_dir / "f.dat").write_bytes(b"content awaiting a successful upload")
    await outputs_manager.port_key_content_changed(port_key)
    with pytest.raises(UploadPortsFailedError):
        await outputs_manager.wait_for_all_uploads_to_finish()

    mock_upload_outputs_raises_error.stop_raising_errors()
    # the failed attempt above recorded nothing: only a later success can fill the list
    assert mock_upload_outputs_raises_error.successful_port_keys == []
    # no new event and no save: the periodic safety sweep notices the unuploaded content
    async for attempt in AsyncRetrying(**_TENACITY_POLL_UPLOADS):
        with attempt:
            assert port_key in mock_upload_outputs_raises_error.successful_port_keys


async def test_content_changed_during_upload_is_reuploaded_without_new_event(
    pausable_upload: PausableUpload,
    single_port_manager: tuple[OutputsManager, Path],
):
    outputs_manager, port_dir = single_port_manager
    _write_port_content(port_dir, b"v1")

    await outputs_manager.port_key_content_changed("output_1")
    await asyncio.wait_for(pausable_upload.started.wait(), timeout=10)

    (port_dir / "f.dat").write_bytes(b"v2 changed during the put while the watcher slept")
    pausable_upload.release.set()

    await outputs_manager.wait_for_all_uploads_to_finish()
    assert pausable_upload.calls.count(["output_1"]) == 2


async def test_content_change_event_during_upload_uploads_the_change_once_the_put_completes(
    pausable_upload: PausableUpload,
    single_port_manager: tuple[OutputsManager, Path],
):
    """the running upload is never cancelled: the event re-arms a check that uploads after it"""
    outputs_manager, port_dir = single_port_manager
    _write_port_content(port_dir, b"v1")

    await outputs_manager.port_key_content_changed("output_1")
    await asyncio.wait_for(pausable_upload.started.wait(), timeout=10)

    (port_dir / "f.dat").write_bytes(b"v2 arrived while the first upload was in flight")
    outputs_manager.on_port_key_change("output_1")
    await asyncio.sleep(_SHORT_QUIET_S * 2)  # let the quiet check notice the change
    pausable_upload.release.set()

    await outputs_manager.wait_for_all_uploads_to_finish()
    assert pausable_upload.calls.count(["output_1"]) == 2


async def test_reverted_content_after_a_replaced_put_is_uploaded_anyway(
    pausable_upload: PausableUpload,
    single_port_manager: tuple[OutputsManager, Path],
):
    """a PUT ships bytes no scan verified, so the earlier certification of the reverted content is void"""
    outputs_manager, port_dir = single_port_manager
    v1 = b"v1 certified by the first upload"
    v2 = b"v2 shipped by the replacement put"
    _write_port_content(port_dir, v1)

    outputs_manager.on_port_key_change("output_1")
    await asyncio.wait_for(pausable_upload.started.wait(), timeout=10)
    pausable_upload.release.set()
    await outputs_manager.wait_for_all_uploads_to_finish()
    assert pausable_upload.calls.count(["output_1"]) == 1

    pausable_upload.started.clear()
    pausable_upload.release.clear()
    _write_port_content(port_dir, v2)
    outputs_manager.on_port_key_change("output_1")
    await asyncio.wait_for(pausable_upload.started.wait(), timeout=10)

    _write_port_content(port_dir, v1)  # the content returns to the certified state while the PUT ships v2
    pausable_upload.release.set()

    # the PUT stored bytes no scan verified: the v1 certification is void
    await asyncio.wait_for(pausable_upload.started.wait(), timeout=10)
    pausable_upload.release.set()
    await outputs_manager.wait_for_all_uploads_to_finish()
    assert pausable_upload.calls.count(["output_1"]) == 3


async def test_background_never_uploads_empty_content_that_was_never_uploaded(
    pausable_upload: PausableUpload,
    single_port_manager: tuple[OutputsManager, Path],
):
    outputs_manager, _port_dir = single_port_manager
    # the port directory does not exist and nothing was uploaded in this session
    outputs_manager.on_port_key_change("output_1")
    await asyncio.sleep(_SHORT_QUIET_S * 3)

    # the empty scan is stable, but uploading it would clear remote data this session never wrote
    assert pausable_upload.calls == []


async def test_deleting_an_uploaded_port_directory_clears_it_in_the_background(
    pausable_upload: PausableUpload,
    single_port_manager: tuple[OutputsManager, Path],
):
    outputs_manager, port_dir = single_port_manager
    _write_port_content(port_dir, b"v1")
    outputs_manager.on_port_key_change("output_1")
    await asyncio.wait_for(pausable_upload.started.wait(), timeout=10)
    pausable_upload.release.set()
    await outputs_manager.wait_for_all_uploads_to_finish()
    assert pausable_upload.calls.count(["output_1"]) == 1

    pausable_upload.started.clear()
    shutil.rmtree(port_dir)
    outputs_manager.on_port_key_change("output_1")

    # the port settled empty and this session certified content: the empty upload clears the remote
    await asyncio.wait_for(pausable_upload.started.wait(), timeout=10)
    await outputs_manager.wait_for_all_uploads_to_finish()

    assert pausable_upload.calls.count(["output_1"]) >= 2
    watch = outputs_manager._port_watches["output_1"]  # noqa: SLF001
    assert watch.trust.is_certified(monitor_module.EMPTY_PORT_FINGERPRINT)


async def test_deleting_the_directory_during_the_put_still_clears_the_remote(
    pausable_upload: PausableUpload,
    single_port_manager: tuple[OutputsManager, Path],
):
    outputs_manager, port_dir = single_port_manager
    _write_port_content(port_dir, b"v1")
    outputs_manager.on_port_key_change("output_1")
    await asyncio.wait_for(pausable_upload.started.wait(), timeout=10)

    # the PUT ships v1 and the directory is gone before it completes: the PUT certifies nothing
    shutil.rmtree(port_dir)
    pausable_upload.started.clear()
    pausable_upload.release.set()

    # the re-armed check settles on empty: the session already stored content, so the clear runs without a save
    await asyncio.wait_for(pausable_upload.started.wait(), timeout=10)
    assert pausable_upload.calls.count(["output_1"]) == 2

    watch = outputs_manager._port_watches["output_1"]  # noqa: SLF001
    async for attempt in AsyncRetrying(**_TENACITY_POLL_UPLOADS):
        with attempt:
            assert watch.trust.is_certified(monitor_module.EMPTY_PORT_FINGERPRINT), (
                "the empty clear was never certified"
            )


async def test_safety_sweep_finds_a_port_that_never_delivered_an_event(
    with_short_sweep: None,
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    outputs_path: Path,
    port_keys: list[str],
):
    for port_key in port_keys:
        (outputs_path / port_key).mkdir()
    (outputs_path / port_keys[0] / "f.dat").write_bytes(b"content nobody announced")

    # no event and no save ever touched this port: only the sweep can discover it
    async for attempt in AsyncRetrying(**_TENACITY_POLL_UPLOADS):
        with attempt:
            assert port_keys[0] in _uploaded_port_keys(mock_upload_outputs)


async def test_disabled_output_io_stops_sweeps_and_quiet_scheduling(
    with_short_sweep: None,
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    outputs_path: Path,
    port_keys: list[str],
):
    outputs_manager.set_background_uploads_enabled(is_enabled=False)
    for port_key in port_keys:
        (outputs_path / port_key).mkdir()
    (outputs_path / port_keys[0] / "f.dat").write_bytes(b"written while output IO is disabled")

    await asyncio.sleep(_SLEEP_PAST_SWEEPS_S)
    assert _uploaded_port_keys(mock_upload_outputs) == []

    outputs_manager.set_background_uploads_enabled(is_enabled=True)
    async for attempt in AsyncRetrying(**_TENACITY_POLL_UPLOADS):
        with attempt:
            assert port_keys[0] in _uploaded_port_keys(mock_upload_outputs)


async def test_save_uploads_while_output_io_is_disabled(
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    port_keys: list[str],
):
    outputs_manager.set_background_uploads_enabled(is_enabled=False)
    await outputs_manager.port_key_content_changed(port_keys[0])
    await outputs_manager.wait_for_all_uploads_to_finish()
    assert port_keys[0] in _uploaded_port_keys(mock_upload_outputs)


async def test_port_key_tracker_add_pending(port_key_tracker: _PortKeyTracker, port_keys: list[str]):
    for key in port_keys:
        await port_key_tracker.add_pending(key)
        assert key in port_key_tracker._pending_port_keys  # noqa: SLF001
    for key in port_keys:
        assert key not in port_key_tracker._uploading_port_keys  # noqa: SLF001


async def test_port_key_tracker_add_pending_unless_uploading(port_key_tracker: _PortKeyTracker):
    assert await port_key_tracker.add_pending_unless_uploading("port_a") is True
    assert "port_a" in port_key_tracker._pending_port_keys  # noqa: SLF001

    await port_key_tracker.move_all_ports_to_uploading()

    # the port is uploading: the schedule request is refused inside the same lock
    assert await port_key_tracker.add_pending_unless_uploading("port_a") is False
    assert "port_a" not in port_key_tracker._pending_port_keys  # noqa: SLF001


async def test_port_key_tracker_are_pending_ports_uploading(
    port_key_tracker_with_ports: _PortKeyTracker, port_keys: list[str]
):
    await port_key_tracker_with_ports.move_all_ports_to_uploading()

    assert await port_key_tracker_with_ports.are_pending_ports_uploading() is False

    for port_key in port_keys:
        await port_key_tracker_with_ports.add_pending(port_key)
    assert await port_key_tracker_with_ports.are_pending_ports_uploading() is True


async def test_port_key_tracker_can_schedule_ports_to_upload(
    port_key_tracker_with_ports: _PortKeyTracker,
):
    assert await port_key_tracker_with_ports.can_schedule_ports_to_upload() is True

    await port_key_tracker_with_ports.move_all_ports_to_uploading()

    assert await port_key_tracker_with_ports.can_schedule_ports_to_upload() is False


async def test_port_key_tracker_move_all_ports_to_uploading(
    port_key_tracker_with_ports: _PortKeyTracker,
):
    previous_pending = set(port_key_tracker_with_ports._pending_port_keys)  # noqa: SLF001
    assert len(port_key_tracker_with_ports._uploading_port_keys) == 0  # noqa: SLF001
    await port_key_tracker_with_ports.move_all_ports_to_uploading()
    assert len(port_key_tracker_with_ports._pending_port_keys) == 0  # noqa: SLF001
    assert port_key_tracker_with_ports._uploading_port_keys == previous_pending  # noqa: SLF001


async def test_port_key_tracker_move_all_uploading_to_pending(
    port_key_tracker_with_ports: _PortKeyTracker,
):
    initial_pending = set(port_key_tracker_with_ports._pending_port_keys)  # noqa: SLF001
    initial_uploading = set(port_key_tracker_with_ports._uploading_port_keys)  # noqa: SLF001

    assert len(port_key_tracker_with_ports._uploading_port_keys) == 0  # noqa: SLF001
    await port_key_tracker_with_ports.move_all_uploading_to_pending()
    assert port_key_tracker_with_ports._pending_port_keys == initial_pending  # noqa: SLF001
    assert port_key_tracker_with_ports._uploading_port_keys == initial_uploading  # noqa: SLF001

    assert len(port_key_tracker_with_ports._uploading_port_keys) == 0  # noqa: SLF001
    await port_key_tracker_with_ports.move_all_ports_to_uploading()
    await port_key_tracker_with_ports.move_all_uploading_to_pending()
    assert port_key_tracker_with_ports._pending_port_keys == initial_pending  # noqa: SLF001
    assert port_key_tracker_with_ports._uploading_port_keys == initial_uploading  # noqa: SLF001


async def test_port_key_tracker_remove_all_uploading(
    port_key_tracker_with_ports: _PortKeyTracker,
):
    initial_pending = set(port_key_tracker_with_ports._pending_port_keys)  # noqa: SLF001
    initial_uploading = set(port_key_tracker_with_ports._uploading_port_keys)  # noqa: SLF001

    assert len(initial_uploading) == 0
    await port_key_tracker_with_ports.move_all_ports_to_uploading()
    assert len(initial_pending) == len(port_key_tracker_with_ports._uploading_port_keys)  # noqa: SLF001

    await port_key_tracker_with_ports.remove_all_uploading()
    assert len(port_key_tracker_with_ports._uploading_port_keys) == 0  # noqa: SLF001


async def test_port_key_tracker_workflow(port_key_tracker: _PortKeyTracker, port_keys: list[str]):
    for port_key in port_keys:
        await port_key_tracker.add_pending(port_key)

    assert await port_key_tracker.are_pending_ports_uploading() is False

    assert await port_key_tracker.can_schedule_ports_to_upload() is True
    await port_key_tracker.move_all_ports_to_uploading()
    expected_uploading = set(port_key_tracker._uploading_port_keys)  # noqa: SLF001
    assert len(expected_uploading) > 0

    assert await port_key_tracker.can_schedule_ports_to_upload() is False

    assert set(await port_key_tracker.get_uploading()) == expected_uploading


async def test_regression_io_log_redirect_cb(
    mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, faker: Faker
):
    for mock_empty_str in (
        "RABBIT_HOST",
        "RABBIT_USER",
        "RABBIT_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ):
        monkeypatch.setenv(mock_empty_str, "")
    monkeypatch.setenv("RABBIT_SECURE", "false")

    mounted_volumes = MountedVolumes(
        service_run_id=ServiceRunID.get_resource_tracking_run_id_for_dynamic(),
        node_id=faker.uuid4(cast_to=None),
        inputs_path=Path("/"),
        outputs_path=Path("/"),
        user_preferences_path=None,
        state_paths=[],
        state_exclude=set(),
        compose_namespace="",
        dy_volumes=Path("/"),
    )

    app = FastAPI()

    # setup settings
    app.state.settings = ApplicationSettings.create_from_envs()

    # mocked_volumes
    app.state.mounted_volumes = mounted_volumes

    app_lifespan: LifespanManager[FastAPI] = LifespanManager()
    configure_outputs_context(app_lifespan)
    configure_outputs_manager(app_lifespan)

    async with app_lifespan(app), TestClient(app):
        outputs_manager: OutputsManager = app.state.outputs_manager
        assert outputs_manager.io_log_redirect_cb is not None

        # ensure callback signature passed to nodeports does not change
        assert isinstance(outputs_manager.io_log_redirect_cb, functools.partial)
        argspec = inspect.getfullargspec(outputs_manager.io_log_redirect_cb.func)
        assert argspec.args == ["app", "log"]
        assert argspec.varargs is None
        assert argspec.varkw is None
        assert argspec.defaults is None
        assert argspec.kwonlyargs == ["log_level"]
        assert argspec.kwonlydefaults is None
        assert argspec.annotations == {
            "return": None,
            "app": FastAPI,
            "log": LogMessageStr,
            "log_level": LogLevelInt,
        }

        # ensure logger used in nodeports deos not change
        assert inspect.getfullargspec(LogRedirectCB.__call__) == FullArgSpec(
            args=["self", "log"],
            varargs=None,
            varkw=None,
            defaults=None,
            kwonlyargs=[],
            kwonlydefaults=None,
            annotations={
                "return": None,
                "log": str,
            },
        )


async def test_raising_post_upload_check_does_not_wedge_the_manager(
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    mocker: MockerFixture,
):
    verify = mocker.patch.object(
        PortUploadTrust,
        "verify_upload_completed",
        new_callable=AsyncMock,
        side_effect=RuntimeError("mocked_check_raised"),
    )

    await outputs_manager.port_key_content_changed(port_keys[0])
    await outputs_manager.wait_for_all_uploads_to_finish()

    # an unawaited check failure must not leave a port in `uploading`: that blocks every later upload
    assert await outputs_manager._port_key_tracker.get_uploading() == []  # noqa: SLF001

    verify.side_effect = None
    verify.return_value = True
    uploads_before = len(mock_upload_outputs.call_args_list)

    await outputs_manager.port_key_content_changed(port_keys[0])
    await outputs_manager.wait_for_all_uploads_to_finish()

    assert len(mock_upload_outputs.call_args_list) > uploads_before


async def test_upload_that_certified_nothing_is_uploaded_again(
    mock_upload_outputs: AsyncMock,
    with_short_quiet: None,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    outputs_path: Path,
    mocker: MockerFixture,
) -> None:
    port_key = port_keys[0]
    port_dir = outputs_path / port_key
    port_dir.mkdir(parents=True, exist_ok=True)
    (port_dir / "f.dat").write_bytes(b"content the first upload could not identify")
    watch = outputs_manager._get_port_watch(port_key)  # noqa: SLF001
    assert watch is not None
    real_stable_fingerprint = watch.monitor.stable_fingerprint

    uncertified = True

    def _stable_fingerprint_uncertified_once() -> str | None:
        # the first PUT races a write: the scan offers no candidate, so it archives unknown bytes
        nonlocal uncertified
        if uncertified:
            uncertified = False
            return None
        return real_stable_fingerprint()

    mocker.patch.object(watch.monitor, "stable_fingerprint", side_effect=_stable_fingerprint_uncertified_once)

    await outputs_manager.port_key_content_changed(port_key)
    await outputs_manager.wait_for_all_uploads_to_finish()

    async for attempt in AsyncRetrying(**_TENACITY_POLL_UPLOADS):
        with attempt:
            assert _uploaded_port_keys(mock_upload_outputs).count(port_key) >= 2


async def test_slow_safety_sweep_on_one_port_does_not_delay_another_port(
    mock_upload_outputs: AsyncMock,
    with_short_quiet: None,
    outputs_path: Path,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    mocker: MockerFixture,
) -> None:
    if len(port_keys) < 2:
        pytest.skip("needs one blocked and one healthy port")

    release = asyncio.Event()
    slow_watch = outputs_manager._get_port_watch(port_keys[0])  # noqa: SLF001
    assert slow_watch is not None
    slow_monitor = slow_watch.monitor
    real_scan = monitor_module.PortContentMonitor._scan  # noqa: SLF001

    async def _scan_when_slow(self, *args, **kwargs) -> _ScanResult:
        if self is slow_monitor:
            await release.wait()
            return _ScanResult(fingerprint="blocked", pending_hashes=0)
        return await real_scan(self, *args, **kwargs)

    mocker.patch.object(monitor_module.PortContentMonitor, "_scan", new=_scan_when_slow)

    outputs_manager.set_all_ports_for_upload()
    await asyncio.sleep(outputs_manager.task_monitor_interval_s * 5)  # let the sweep block
    for port_key in port_keys:
        _write_port_content(outputs_path / port_key, b"content")
        outputs_manager.on_port_key_change(port_key)

    healthy_port_key = port_keys[1]
    async for attempt in AsyncRetrying(**_TENACITY_POLL_UPLOADS):
        with attempt:
            assert healthy_port_key in _uploaded_port_keys(mock_upload_outputs)

    # the blocked port never settled, so nothing may certify it as uploaded
    assert port_keys[0] not in _uploaded_port_keys(mock_upload_outputs)

    release.set()
