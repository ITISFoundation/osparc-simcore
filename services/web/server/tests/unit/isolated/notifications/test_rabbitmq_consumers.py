# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from models_library.progress_bar import ProgressReport
from models_library.rabbitmq_messages import (
    ProgressRabbitMessageNode,
    ProgressRabbitMessageProject,
    ProgressType,
)
from models_library.socketio import SocketMessageDict
from pytest_mock import MockerFixture
from simcore_service_webserver.notifications._rabbitmq_exclusive_queue_consumers import (
    _progress_message_parser,
)
from simcore_service_webserver.socketio.models import WebSocketNodeProgress


@pytest.mark.parametrize(
    "raw_data, expected_socket_message",
    [
        pytest.param(
            ProgressRabbitMessageNode(
                project_id=UUID("ee825037-599b-4df1-ba44-731dd48287fa"),
                user_id=123,
                node_id=UUID("6925403d-5464-4d92-9ec9-72c5793ca203"),
                progress_type=ProgressType.SERVICE_OUTPUTS_PULLING,
                report=ProgressReport(actual_value=0.4, total=1),
            ).model_dump_json(),
            SocketMessageDict(
                event_type=WebSocketNodeProgress.get_event_type(),
                data={
                    "project_id": "ee825037-599b-4df1-ba44-731dd48287fa",
                    "node_id": "6925403d-5464-4d92-9ec9-72c5793ca203",
                    "user_id": 123,
                    "progress_type": ProgressType.SERVICE_OUTPUTS_PULLING.value,
                    "progress_report": {
                        "actual_value": 0.4,
                        "total": 1.0,
                        "unit": None,
                        "message": None,
                    },
                },
            ),
            id="node_progress",
        ),
        pytest.param(
            ProgressRabbitMessageProject(
                project_id=UUID("ee825037-599b-4df1-ba44-731dd48287fa"),
                user_id=123,
                progress_type=ProgressType.PROJECT_CLOSING,
                report=ProgressReport(actual_value=0.4, total=1),
            ).model_dump_json(),
            SocketMessageDict(
                event_type=WebSocketNodeProgress.get_event_type(),
                data={
                    "project_id": "ee825037-599b-4df1-ba44-731dd48287fa",
                    "user_id": 123,
                    "progress_type": ProgressType.PROJECT_CLOSING.value,
                    "progress_report": {
                        "actual_value": 0.4,
                        "total": 1.0,
                        "unit": None,
                        "message": None,
                    },
                },
            ),
            id="project_progress",
        ),
    ],
)
async def test_regression_progress_message_parser(
    mocker: MockerFixture, raw_data: bytes, expected_socket_message: SocketMessageDict
):
    send_messages_to_user_mock = mocker.patch(
        "simcore_service_webserver.notifications._rabbitmq_exclusive_queue_consumers.send_message_to_user",
        autospec=True,
    )

    app = AsyncMock()
    assert await _progress_message_parser(app, raw_data)

    # tests how send_message_to_user is called
    assert send_messages_to_user_mock.call_count == 1
    message = send_messages_to_user_mock.call_args.kwargs["message"]

    # check that all fields are sent as expected
    assert message["data"] == expected_socket_message["data"]
