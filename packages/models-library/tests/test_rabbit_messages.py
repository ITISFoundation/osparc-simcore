import pytest
from faker import Faker
from models_library.progress_bar import ProgressReport
from models_library.rabbitmq_messages import (
    ProgressRabbitMessageNode,
    ProgressRabbitMessageProject,
    ProgressRabbitMessageWorkerJob,
    ProgressType,
)
from pydantic import TypeAdapter

faker = Faker()


@pytest.mark.parametrize(
    "raw_data, class_type",
    [
        pytest.param(
            ProgressRabbitMessageNode(
                project_id=faker.uuid4(cast_to=None),
                user_id=faker.pyint(min_value=1),
                node_id=faker.uuid4(cast_to=None),
                progress_type=ProgressType.SERVICE_OUTPUTS_PULLING,
                report=ProgressReport(actual_value=0.4, total=1),
            ).model_dump_json(),
            ProgressRabbitMessageNode,
            id="node_progress",
        ),
        pytest.param(
            ProgressRabbitMessageProject(
                project_id=faker.uuid4(cast_to=None),
                user_id=faker.pyint(min_value=1),
                progress_type=ProgressType.PROJECT_CLOSING,
                report=ProgressReport(actual_value=0.4, total=1),
            ).model_dump_json(),
            ProgressRabbitMessageProject,
            id="project_progress",
        ),
        pytest.param(
            ProgressRabbitMessageWorkerJob(
                user_id=faker.pyint(min_value=1),
                progress_type=ProgressType.PROJECT_CLOSING,
                report=ProgressReport(actual_value=0.4, total=1),
                osparc_job_id=faker.pystr(),
            ).model_dump_json(),
            ProgressRabbitMessageWorkerJob,
            id="worker_job_progress",
        ),
    ],
)
async def test_raw_message_parsing(raw_data: str, class_type: type):
    result = TypeAdapter(
        ProgressRabbitMessageNode
        | ProgressRabbitMessageProject
        | ProgressRabbitMessageWorkerJob
    ).validate_json(raw_data)
    assert type(result) is class_type
