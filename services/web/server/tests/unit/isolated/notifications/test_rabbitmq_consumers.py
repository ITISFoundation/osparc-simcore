# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from unittest.mock import AsyncMock

import pytest
from faker import Faker
from models_library.progress_bar import ProgressReport
from models_library.rabbitmq_messages import (
    ProgressRabbitMessageNode,
    ProgressRabbitMessageProject,
    ProgressType,
)
from pydantic import BaseModel
from pytest_mock import MockerFixture
from simcore_service_webserver.notifications._rabbitmq_exclusive_queue_consumers import (
    _progress_message_parser,
)

_faker = Faker()


@pytest.mark.parametrize(
    "raw_data, class_type",
    [
        pytest.param(
            ProgressRabbitMessageNode(
                project_id=_faker.uuid4(cast_to=None),
                user_id=_faker.uuid4(cast_to=None),
                node_id=_faker.uuid4(cast_to=None),
                progress_type=ProgressType.SERVICE_OUTPUTS_PULLING,
                report=ProgressReport(actual_value=0.4, total=1),
            ).json(),
            ProgressRabbitMessageNode,
            id="node_progress",
        ),
        pytest.param(
            ProgressRabbitMessageProject(
                project_id=_faker.uuid4(cast_to=None),
                user_id=_faker.uuid4(cast_to=None),
                progress_type=ProgressType.PROJECT_CLOSING,
                report=ProgressReport(actual_value=0.4, total=1),
            ).json(),
            ProgressRabbitMessageProject,
            id="project_progress",
        ),
    ],
)
async def test_regression_progress_message_parser(
    mocker: MockerFixture, raw_data: bytes, class_type: type[BaseModel]
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
    assert class_type.parse_obj(message["data"])
