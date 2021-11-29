# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments

import pytest
from dask_task_models_library.container_tasks.events import (
    BaseTaskEvent,
    TaskCancelEvent,
    TaskLogEvent,
    TaskProgressEvent,
    TaskStateEvent,
)
from models_library.projects_state import RunningState
from pytest_mock.plugin import MockerFixture


def test_task_event_abstract():
    with pytest.raises(TypeError):
        # pylint: disable=abstract-class-instantiated
        BaseTaskEvent(job_id="some_fake")  # type: ignore


@pytest.mark.parametrize(
    "model_cls", [TaskStateEvent, TaskProgressEvent, TaskLogEvent, TaskCancelEvent]
)
def test_events_models_examples(model_cls):
    examples = model_cls.Config.schema_extra["examples"]

    for index, example in enumerate(examples):
        print(f"{index:-^10}:\n", example)

        model_instance = model_cls(**example)
        assert model_instance

        assert model_instance.topic_name()


@pytest.fixture()
def mocked_dask_worker_job_id(mocker: MockerFixture) -> str:
    mock_get_worker = mocker.patch(
        "dask_task_models_library.container_tasks.events.get_worker", autospec=True
    )
    fake_job_id = "some_fake_job_id"
    mock_get_worker.return_value.get_current_task.return_value = fake_job_id
    return fake_job_id


def test_task_state_from_worker(mocked_dask_worker_job_id: str):
    event = TaskStateEvent.from_dask_worker(
        RunningState.FAILED, msg="some test message"
    )
    assert event.job_id == mocked_dask_worker_job_id
    assert event.state == RunningState.FAILED
    assert event.msg == "some test message"


def test_task_progress_from_worker(mocked_dask_worker_job_id: str):
    event = TaskProgressEvent.from_dask_worker(0.7)

    assert event.job_id == mocked_dask_worker_job_id
    assert event.progress == 0.7


def test_task_log_from_worker(mocked_dask_worker_job_id: str):
    event = TaskLogEvent.from_dask_worker(log="here is the amazing logs")

    assert event.job_id == mocked_dask_worker_job_id
    assert event.log == "here is the amazing logs"
