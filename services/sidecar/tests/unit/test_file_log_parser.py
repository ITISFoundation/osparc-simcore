from simcore_service_sidecar.file_log_parser import LogType, parse_line
import pytest


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
    ],
)
async def test_parse_line(log, expected_log_type, expected_parsed_message):
    log_type, log_message = await parse_line(log)
    assert log_type == expected_log_type
    assert log_message == expected_parsed_message
