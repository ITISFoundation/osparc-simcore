from asyncio import Future, ensure_future, sleep
from pathlib import Path

import pytest
from simcore_service_sidecar.log_parser import LogType, monitor_logs_task, parse_line


@pytest.mark.parametrize(
    "log, expected_log_type, expected_parsed_message",
    [
        (
            "[progress] this is some whatever progress without number",
            LogType.LOG,
            "[task] [progress] this is some whatever progress without number",
        ),
        ("[Progress] 34%", LogType.PROGRESS, "0.34"),
        ("[PROGRESS] .34", LogType.PROGRESS, ".34"),
        ("[progress] 0.44", LogType.PROGRESS, "0.44"),
        ("[progress] 44 percent done", LogType.PROGRESS, "0.44"),
        ("[progress] 44/150", LogType.PROGRESS, str(44.0 / 150.0)),
        (
            "Progress: this is some progress",
            LogType.LOG,
            "[task] Progress: this is some progress",
        ),
        ("progress: 34%", LogType.PROGRESS, "0.34"),
        ("PROGRESS: .34", LogType.PROGRESS, ".34"),
        ("progress: 0.44", LogType.PROGRESS, "0.44"),
        ("progress: 44 percent done", LogType.PROGRESS, "0.44"),
        ("progress: 44/150", LogType.PROGRESS, str(44.0 / 150.0)),
        (
            "any kind of message even with progress inside",
            LogType.LOG,
            "[task] any kind of message even with progress inside",
        ),
        ("[PROGRESS]1.000000\n", LogType.PROGRESS, "1.000000"),
    ],
)
async def test_parse_line(log, expected_log_type, expected_parsed_message):
    log_type, log_message = await parse_line(log)
    assert log_type == expected_log_type
    assert log_message == expected_parsed_message


def future_with_result(result):
    f = Future()
    f.set_result(result)
    return f


async def test_monitor_log_task(temp_folder: Path, mocker):
    mock_cb = mocker.Mock(return_value=future_with_result(""))
    log_file = temp_folder / "test_log.txt"
    log_file.touch()
    assert log_file.exists()
    task = ensure_future(monitor_logs_task(log_file, mock_cb))
    assert task
    await sleep(2)
    log_file.write_text("this is a test")
    await sleep(2)
    mock_cb.assert_called_once()
    assert task.cancel()
