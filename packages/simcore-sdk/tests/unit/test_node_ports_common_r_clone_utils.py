import json
from unittest.mock import AsyncMock

import pytest
from pydantic import TypeAdapter
from simcore_sdk.node_ports_common.r_clone_utils import (
    SyncProgressLogParser,
    _RCloneSyncMessageBase,
    _RCloneSyncMessages,
    _RCloneSyncTransferCompletedMessage,
    _RCloneSyncTransferringMessage,
    _RCloneSyncUpdatedMessage,
)


@pytest.mark.parametrize(
    "log_message,expected",
    [
        (
            '{"level":"info","msg":"There was nothing to transfer","source":"sync/sync.go:954","time":"2024-09-25T10:18:04.904537+00:00"}',
            _RCloneSyncMessageBase,
        ),
        (
            '{"level":"info","msg":"","object":".hidden_do_not_remove","objectType":"*s3.Object","source":"operations/operations.go:277","time":"2024-09-24T07:11:22.147117+00:00"}',
            _RCloneSyncUpdatedMessage,
        ),
        (
            '{"level":"info","msg":"Copied (new)","object":"README.ipynb","objectType":"*s3.Object","size":5123,"source":"operations/copy.go:360","time":"2024-04-23T14:05:10.408277+00:00"}',
            _RCloneSyncTransferCompletedMessage,
        ),
        (
            json.dumps(
                {
                    "level": "",
                    "msg": "",
                    "source": "",
                    "time": "2024-09-24T07:11:22.147117+00:00",
                    "object": "str",
                }
            ),
            _RCloneSyncUpdatedMessage,
        ),
        (
            json.dumps(
                {
                    "level": "",
                    "msg": "",
                    "source": "",
                    "time": "2024-09-24T07:11:22.147117+00:00",
                    "object": "str",
                    "size": 1,
                }
            ),
            _RCloneSyncTransferCompletedMessage,
        ),
        (
            json.dumps(
                {
                    "level": "",
                    "msg": "",
                    "source": "",
                    "time": "2024-09-24T07:11:22.147117+00:00",
                    "stats": {"bytes": 1, "totalBytes": 1},
                }
            ),
            _RCloneSyncTransferringMessage,
        ),
    ],
)
async def test_rclone_stbc_message_parsing_regression(log_message: str, expected: type):
    parsed_log = TypeAdapter(_RCloneSyncMessages).validate_json(log_message)
    assert isinstance(parsed_log, expected)

    progress_log_parser = SyncProgressLogParser(AsyncMock())
    await progress_log_parser(log_message)
