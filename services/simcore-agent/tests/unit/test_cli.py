# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import signal
import traceback
from multiprocessing import Process
from os import getpid, kill
from threading import Timer

import pytest
from _pytest.logging import LogCaptureFixture
from click.testing import Result
from simcore_service_simcore_agent._app import Application
from simcore_service_simcore_agent._meta import (
    APP_FINISHED_BANNER_MSG,
    APP_STARTED_BANNER_MSG,
)
from simcore_service_simcore_agent.cli import main
from typer.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def _format_cli_error(result: Result) -> str:
    assert result.exception
    tb_message = "\n".join(traceback.format_tb(result.exception.__traceback__))
    return f"Below exception was raised by the cli:\n{tb_message}"


@pytest.mark.parametrize("signal", Application.HANDLED_EXIT_SIGNALS)
def test_process_handles_signals(
    env: None,
    cli_runner: CliRunner,
    signal: signal.Signals,
    caplog_info_debug: LogCaptureFixture,
):

    # Running out app in SubProcess and after a while using signal sending
    # SIGINT, results passed back via channel/queue
    def background():
        Timer(0.2, lambda: kill(getpid(), signal)).start()
        result = cli_runner.invoke(main, ["run"])
        print(result.output)

        assert result.exit_code == 0, _format_cli_error(result)
        assert APP_FINISHED_BANNER_MSG in caplog_info_debug.messages
        assert APP_STARTED_BANNER_MSG in caplog_info_debug.messages

    process = Process(target=background)
    process.start()
    process.join()

    assert process.exitcode == 0, "Please check logs above for error"
