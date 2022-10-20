# pylint: disable=redefined-outer-name

import signal
from multiprocessing import Process, Queue
from os import getpid, kill
from threading import Timer

import pytest
from simcore_service_simcore_agent._meta import (
    APP_FINISHED_BANNER_MSG,
    APP_STARTED_BANNER_MSG,
)
from simcore_service_simcore_agent.app import Application
from simcore_service_simcore_agent.cli import main
from typer.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.mark.parametrize("signal", Application.HANDLED_EXIT_SIGNALS)
def test_process_handles_signals(cli_runner: CliRunner, signal: signal.Signals):
    queue = Queue()

    # Running out app in SubProcess and after a while using signal sending
    # SIGINT, results passed back via channel/queue
    def background():
        Timer(0.2, lambda: kill(getpid(), signal)).start()
        result = cli_runner.invoke(main, ["run"])
        queue.put(result.exit_code)
        queue.put(result.output)

    process = Process(target=background)
    process.start()
    process.join()

    exit_code = queue.get()
    output = queue.get()

    assert exit_code == 0
    assert APP_STARTED_BANNER_MSG in output
    assert APP_FINISHED_BANNER_MSG in output
