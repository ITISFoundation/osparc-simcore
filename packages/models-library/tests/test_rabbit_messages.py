from typing import Union

import pytest
from faker import Faker
from models_library.progress_bar import ProgressReport
from models_library.rabbitmq_messages import (
    ProgressRabbitMessageNode,
    ProgressRabbitMessageProject,
    ProgressType,
)
from pydantic import parse_raw_as

faker = Faker()


@pytest.mark.parametrize(
    "raw_data, class_type",
    [
        pytest.param(
            ProgressRabbitMessageNode(
                project_id=faker.uuid4(cast_to=None),
                user_id=faker.uuid4(cast_to=None),
                node_id=faker.uuid4(cast_to=None),
                progress_type=ProgressType.SERVICE_OUTPUTS_PULLING,
                report=ProgressReport(actual_value=0.4, total=1),
            ).json(),
            ProgressRabbitMessageNode,
            id="node_progress",
        ),
        pytest.param(
            ProgressRabbitMessageProject(
                project_id=faker.uuid4(cast_to=None),
                user_id=faker.uuid4(cast_to=None),
                progress_type=ProgressType.PROJECT_CLOSING,
                report=ProgressReport(actual_value=0.4, total=1),
            ).json(),
            ProgressRabbitMessageProject,
            id="project_progress",
        ),
    ],
)
async def test_raw_message_parsing(raw_data: str, class_type: type):
    result = parse_raw_as(
        Union[ProgressRabbitMessageNode, ProgressRabbitMessageProject],
        raw_data,
    )
    assert type(result) == class_type
