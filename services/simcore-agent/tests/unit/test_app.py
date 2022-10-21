# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import asyncio
import logging
import pickle
import socket
import threading
from logging.handlers import DatagramHandler
from multiprocessing import Process
from time import sleep
from typing import Final, Iterator, Optional

import pytest
from pydantic import PositiveFloat
from pytest import LogCaptureFixture
from simcore_service_simcore_agent.app import Application

REPEAT_TASK_INTERVAL_S: Final[PositiveFloat] = 0.05
SOCKET_ADDRESS: tuple[str, int] = ("127.0.0.1", 2001)

_EXIT_MARK: Final[bytes] = b"exit"


@pytest.fixture
def log_receiver() -> Iterator[None]:
    def _worker():
        listening_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listening_socket.bind(SOCKET_ADDRESS)

        while True:
            data = listening_socket.recv(4096)
            if data == _EXIT_MARK:
                break
            # Dont forget to skip over the 32-bit length prepended
            decided_data = pickle.loads(data[4:])

            # log message in the context of this process
            record = logging.makeLogRecord(decided_data)
            logger = logging.getLogger(record.name)
            logger.handle(record)

        listening_socket.close()

    thread = threading.Thread(target=_worker)
    thread.start()

    yield None

    shutdown_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    shutdown_socket.sendto(_EXIT_MARK, SOCKET_ADDRESS)

    thread.join()


@pytest.mark.parametrize("repeat_interval_s", [REPEAT_TASK_INTERVAL_S, None])
def test_app_recovers_from_error(
    log_receiver: None,
    caplog_info_debug: LogCaptureFixture,
    repeat_interval_s: Optional[PositiveFloat],
):
    async def _error_raising_job() -> None:
        raise RuntimeError("raised expected error")

    def _worker(loop):
        handler = DatagramHandler(*SOCKET_ADDRESS)
        handler.setLevel(logging.DEBUG)
        logging.root.addHandler(handler)

        app = Application(loop)
        app.add_job(_error_raising_job, repeat_interval_s=repeat_interval_s)
        app.run()

    process = Process(target=_worker, args=(asyncio.get_event_loop(),), daemon=True)
    process.start()
    sleep(REPEAT_TASK_INTERVAL_S * 10)
    process.kill()

    log_messages = "\n".join(caplog_info_debug.messages)
    print(log_messages)

    assert f"Running '{_error_raising_job.__name__}'" in log_messages
    assert 'RuntimeError("raised expected error")' in log_messages
    assert (
        f"Will run '{_error_raising_job.__name__}' again in {repeat_interval_s} seconds"
        in log_messages
    )
    if repeat_interval_s is None:
        assert (
            f"Unexpected termination of '{_error_raising_job.__name__}'; it will be restarted"
            in log_messages
        )
