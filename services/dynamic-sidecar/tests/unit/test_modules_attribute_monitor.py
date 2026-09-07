# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access


import asyncio
import logging
import multiprocessing
import pickle
import socket
import threading
from collections import deque
from collections.abc import AsyncIterator, Iterator
from logging.handlers import DEFAULT_UDP_LOGGING_PORT, DatagramHandler
from multiprocessing.queues import Queue
from pathlib import Path
from typing import Final
from unittest.mock import AsyncMock, Mock

import pytest
from faker import Faker
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from models_library.basic_types import PortInt
from pydantic import PositiveFloat
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.core.utils import async_command
from simcore_service_dynamic_sidecar.modules.attribute_monitor import (
    _logging_event_handler,
    configure_attribute_monitor,
)
from simcore_service_dynamic_sidecar.modules.attribute_monitor._logging_event_handler import (
    _LoggingEventHandlerProcess,
)

# NOTE: multiprocessing logs do not work with logcap,
# redirecting via UDP, below is a slight change from
# https://github.com/pytest-dev/pytest/issues/3037#issuecomment-745050393

DATAGRAM_PORT: Final[PortInt] = PortInt(DEFAULT_UDP_LOGGING_PORT)
ENSURE_LOGS_DELIVERED: Final[float] = 0.1


@pytest.fixture
def fake_dy_volumes_mount_dir(tmp_path: Path) -> Path:
    assert tmp_path.exists()
    return tmp_path


@pytest.fixture
def patch_logging(mocker: MockerFixture) -> None:
    logger = logging.getLogger(_logging_event_handler.__name__)
    datagram_handler = DatagramHandler("127.0.0.1", DATAGRAM_PORT)
    datagram_handler.setLevel(logging.NOTSET)
    logger.addHandler(datagram_handler)
    logger.isEnabledFor = lambda _level: True

    mocker.patch.object(_logging_event_handler, "logger", logger)


class LogRecordKeeper:
    def __init__(self) -> None:
        self._records = deque()

    def appendleft(self, x) -> None:
        self._records.appendleft(x)

    def has_log_within(self, **expected_logrec_fields) -> bool:
        for rec in self._records:
            if all(str(v) in str(rec[k]) for k, v in expected_logrec_fields.items()):
                return True
        return False

    def __len__(self) -> int:
        return len(self._records)

    def __repr__(self) -> str:
        return f"<{LogRecordKeeper.__name__} {self._records}>"


@pytest.fixture
def log_receiver() -> Iterator[LogRecordKeeper]:
    log_record_keeper = LogRecordKeeper()

    def listener() -> None:
        receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receive_socket.bind(("127.0.0.1", DATAGRAM_PORT))
        while True:
            data = receive_socket.recv(4096)
            if data == b"die":
                break
            # Dont forget to skip over the 32-bit length prepended
            logrec = pickle.loads(data[4:])
            log_record_keeper.appendleft(logrec)

    receiver_thread = threading.Thread(target=listener)
    receiver_thread.start()

    yield log_record_keeper

    close_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    close_socket.sendto(b"die", ("127.0.0.1", DATAGRAM_PORT))
    receiver_thread.join()


@pytest.fixture
def fake_app(fake_dy_volumes_mount_dir: Path, patch_logging: None) -> FastAPI:
    fake_settings = AsyncMock()
    fake_settings.DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR = fake_dy_volumes_mount_dir

    app = FastAPI()
    app.state.settings = fake_settings
    return app


@pytest.fixture
async def logging_event_handler_observer(
    fake_app: FastAPI,
) -> AsyncIterator[None]:
    app_lifespan: LifespanManager[FastAPI] = LifespanManager()
    configure_attribute_monitor(app_lifespan)
    async with app_lifespan(fake_app):
        assert fake_app.state.attribute_monitor
        yield None


@pytest.fixture
def health_check_queue() -> Queue[int | None]:
    return multiprocessing.Queue()


@pytest.fixture
def heart_beat_interval_s() -> PositiveFloat:
    return 0.01


def test_logging_event_handler_process_concurrent_stop_process_does_not_raise(
    fake_dy_volumes_mount_dir: Path,
    health_check_queue: Queue[int | None],
    heart_beat_interval_s: PositiveFloat,
):
    observer_process = _LoggingEventHandlerProcess(
        path_to_observe=fake_dy_volumes_mount_dir,
        health_check_queue=health_check_queue,
        heart_beat_interval_s=heart_beat_interval_s,
    )

    entered_kill = threading.Event()
    release_kill = threading.Event()
    first_caller_paused = False

    def _kill() -> None:
        nonlocal first_caller_paused
        # only the first caller pauses: it must observe `self._process` as
        # non-`None` for longer than it takes a concurrent caller to clear it
        if not first_caller_paused:
            first_caller_paused = True
            entered_kill.set()
            assert release_kill.wait(timeout=5), "test setup: never released"

    mock_process = Mock()
    mock_process.kill.side_effect = _kill
    observer_process._process = mock_process  # noqa: SLF001

    errors: list[BaseException] = []

    def _stop_process() -> None:
        try:
            observer_process._stop_process()  # noqa: SLF001
        except BaseException as exc:  # pylint: disable=broad-except
            errors.append(exc)

    first_thread = threading.Thread(target=_stop_process)
    first_thread.start()
    assert entered_kill.wait(timeout=5), "first thread never reached kill()"

    # with the lock this blocks on `_process_lock` and cannot make progress
    # while the first thread is paused mid-`kill()`; without it, it runs to
    # completion (clearing `self._process`) before the first thread resumes
    second_thread = threading.Thread(target=_stop_process)
    second_thread.start()
    second_thread.join(timeout=0.5)

    release_kill.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert not first_thread.is_alive(), "first thread never completed (deadlock?)"
    assert not second_thread.is_alive(), "second thread never completed (deadlock?)"
    assert not errors


def test_logging_event_handler_process_concurrent_start_vs_stop_process_does_not_raise(
    fake_dy_volumes_mount_dir: Path,
    health_check_queue: Queue[int | None],
    heart_beat_interval_s: PositiveFloat,
    mocker: MockerFixture,
):
    observer_process = _LoggingEventHandlerProcess(
        path_to_observe=fake_dy_volumes_mount_dir,
        health_check_queue=health_check_queue,
        heart_beat_interval_s=heart_beat_interval_s,
    )

    entered_start = threading.Event()
    release_start = threading.Event()
    first_caller_paused = False

    def _start() -> None:
        nonlocal first_caller_paused
        # pauses while `start_process` still holds `_process_lock`
        if not first_caller_paused:
            first_caller_paused = True
            entered_start.set()
            assert release_start.wait(timeout=5), "test setup: never released"

    mock_process_cls = Mock()
    mock_process_cls.return_value.start.side_effect = _start
    mocker.patch.object(multiprocessing, "Process", mock_process_cls)

    errors: list[BaseException] = []

    def _start_process() -> None:
        try:
            observer_process.start_process()
        except BaseException as exc:  # pylint: disable=broad-except
            errors.append(exc)

    def _stop_process() -> None:
        try:
            observer_process._stop_process()  # noqa: SLF001
        except BaseException as exc:  # pylint: disable=broad-except
            errors.append(exc)

    start_thread = threading.Thread(target=_start_process)
    start_thread.start()
    assert entered_start.wait(timeout=5), "start thread never reached start()"

    # must block on `_process_lock` while `start_process` is still in progress
    stop_thread = threading.Thread(target=_stop_process)
    stop_thread.start()
    stop_thread.join(timeout=0.5)
    assert stop_thread.is_alive(), "_stop_process proceeded before start_process released the lock"

    release_start.set()
    start_thread.join(timeout=5)
    stop_thread.join(timeout=5)

    assert not start_thread.is_alive(), "start thread never completed (deadlock?)"
    assert not stop_thread.is_alive(), "stop thread never completed (deadlock?)"
    assert not errors


@pytest.mark.parametrize(
    "command_template",
    [
        pytest.param("chown {uid}:{gid} {path}", id="chown"),
        pytest.param("chmod +x {path}", id="chmod"),
    ],
)
async def test_chown_triggers_event(
    mock_ensure_read_permissions_on_user_service_data: None,
    logging_event_handler_observer: None,
    fake_dy_volumes_mount_dir: Path,
    command_template: str,
    faker: Faker,
    log_receiver: LogRecordKeeper,
):
    file_path = fake_dy_volumes_mount_dir / f"test_file_{faker.uuid4()}"
    file_path.write_text(faker.text())
    file_stat = file_path.stat()

    for command in (
        f"ls -lah {file_path}",
        command_template.format(uid=file_stat.st_uid, gid=file_stat.st_gid, path=file_path),
        f"ls -lah {file_path}",
    ):
        command_result = await async_command(command)
        assert command_result.success is True
        print(f"$ {command_result.command}\n{command_result.message}")

    # normally logs get delivered by this point, sleep to make sure they are here
    await asyncio.sleep(ENSURE_LOGS_DELIVERED)
    assert log_receiver.has_log_within(msg=f"Attribute change to: '{file_path}'", levelname="INFO")


@pytest.mark.parametrize("file_is_present", [True, False])
async def test_regression_logging_event_handler_file_does_not_exist(
    faker: Faker,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    file_is_present: bool,
):
    caplog.clear()
    mocked_event = Mock()
    file_path = tmp_path / f"missing-path{faker.uuid4()}"
    if file_is_present:
        file_path.touch()
        assert file_path.exists() is True
    else:
        assert file_path.exists() is False

    mocked_event.src_path = file_path
    _logging_event_handler._LoggingEventHandler().event_handler(  # noqa: SLF001
        mocked_event
    )
    assert (f"Attribute change to: '{file_path}'" in caplog.text) is file_is_present
