# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import logging
import os
import pickle
import socket
import threading
from collections import deque
from pathlib import Path
from typing import Final
from unittest.mock import AsyncMock

import pytest
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from models_library.basic_types import PortInt
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.core.utils import async_command
from simcore_service_dynamic_sidecar.modules.attribute_monitor import (
    _logging_event_handler,
    setup_attribute_monitor,
)

# NOTE: multiprocessing logs do not work with logcap,
# redirecting via UDP, below is a slight change from
# https://github.com/pytest-dev/pytest/issues/3037#issuecomment-745050393

DATAGRAM_PORT: Final[PortInt] = logging.handlers.DEFAULT_UDP_LOGGING_PORT
ENSURE_LOGS_DELIVERED: Final[float] = 0.1


@pytest.fixture
def fake_dy_volumes_mount_dir(tmp_path: Path) -> Path:
    assert tmp_path.exists()
    return tmp_path


@pytest.fixture
def patch_logging(mocker: MockerFixture) -> None:
    logger = logging.getLogger(_logging_event_handler.__name__)
    datagram_handler = logging.handlers.DatagramHandler("127.0.0.1", DATAGRAM_PORT)
    datagram_handler.setLevel(logging.NOTSET)
    logger.addHandler(datagram_handler)
    logger.isEnabledFor = lambda _: True

    mocker.patch.object(_logging_event_handler, "logger", logger)


class LogRecordKeeper:
    def __init__(self):
        self._records = deque()

    def appendleft(self, x) -> None:
        self._records.appendleft(x)

    def has_log_within(self, **expected_logrec_fields) -> None:
        for rec in self._records:
            if all(str(v) in str(rec[k]) for k, v in expected_logrec_fields.items()):
                return True
        return False

    def __len__(self) -> int:
        return len(self._records)

    def __repr__(self) -> str:
        return f"<{LogRecordKeeper.__name__} {self._records}>"


@pytest.fixture
def log_receiver() -> LogRecordKeeper:
    log_record_keeper = LogRecordKeeper()

    def listener():
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
) -> None:
    setup_attribute_monitor(fake_app)
    async with LifespanManager(fake_app):
        assert fake_app.state.attribute_monitor
        yield None


@pytest.mark.parametrize(
    "command_template",
    [
        pytest.param("chown {uid}:{uid} {path}", id="chown"),
        pytest.param("chmod +x {path}", id="chmod"),
    ],
)
async def test_chown_triggers_event(
    logging_event_handler_observer: None,
    fake_dy_volumes_mount_dir: Path,
    command_template: str,
    faker: Faker,
    log_receiver: LogRecordKeeper,
):
    file_path = fake_dy_volumes_mount_dir / f"test_file_{faker.uuid4()}"
    file_path.write_text(faker.text())

    for command in (
        f"ls -lah {file_path}",
        command_template.format(uid=os.getuid(), path=file_path),
        f"ls -lah {file_path}",
    ):
        command_result = await async_command(command)
        assert command_result.success is True
        print(f"$ {command_result.command}\n{command_result.message}")

    # normally logs get deliverd by this point, sleep to make sure they are here
    # await asyncio.sleep(ENSURE_LOGS_DELIVERED)
    assert log_receiver.has_log_within(
        msg=f"Attribute change to: '{file_path}'", levelname="INFO"
    )
