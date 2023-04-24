# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

from unittest.mock import AsyncMock

import pytest
from faker import Faker
from models_library.rabbitmq_messages import (
    ProgressRabbitMessageNode,
    ProgressRabbitMessageProject,
    ProgressType,
)
from pytest_mock import MockerFixture
from simcore_service_webserver import computation_subscribe

_faker = Faker()


@pytest.fixture
def mock_send_messages(mocker: MockerFixture) -> dict:
    reference = {}

    async def mock_send_message(*args) -> None:
        reference["args"] = args

    mocker.patch.object(
        computation_subscribe, "send_messages", side_effect=mock_send_message
    )

    yield reference


@pytest.mark.parametrize(
    "raw_data, class_type",
    [
        pytest.param(
            ProgressRabbitMessageNode(
                **{
                    "project_id": _faker.uuid4(cast_to=None),
                    "user_id": _faker.uuid4(cast_to=None),
                    "node_id": _faker.uuid4(cast_to=None),
                    "progress_type": ProgressType.SERVICE_OUTPUTS_PULLING,
                    "progress": 0.4,
                }
            ).json(),
            ProgressRabbitMessageNode,
            id="node_progress",
        ),
        pytest.param(
            ProgressRabbitMessageProject(
                **{
                    "project_id": _faker.uuid4(cast_to=None),
                    "user_id": _faker.uuid4(cast_to=None),
                    "progress_type": ProgressType.PROJECT_CLOSING,
                    "progress": 0.4,
                }
            ).json(),
            ProgressRabbitMessageProject,
            id="project_progress",
        ),
    ],
)
async def test_regression_progress_message_parser(
    mock_send_messages: dict, raw_data: bytes, class_type: type
):
    await computation_subscribe._progress_message_parser(AsyncMock(), raw_data)
    serialized_sent_data = mock_send_messages["args"][2][0]["data"]
    # check that all fields are sent as expected
    assert class_type.parse_obj(serialized_sent_data)
