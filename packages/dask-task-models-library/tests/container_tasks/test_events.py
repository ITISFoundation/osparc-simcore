import pytest
from dask_task_models_library.container_tasks.events import TaskEvent, TaskStateEvent
from models_library.projects_state import RunningState
from pytest_mock.plugin import MockerFixture


def test_task_event_abstract():
    with pytest.raises(TypeError):
        # pylint: disable=abstract-class-instantiated
        TaskEvent(job_id="some_fake")  # type: ignore


@pytest.mark.parametrize("model_cls", [(TaskStateEvent)])
def test_events_models_examples(model_cls):
    examples = model_cls.Config.schema_extra["examples"]

    for index, example in enumerate(examples):
        print(f"{index:-^10}:\n", example)

        model_instance = model_cls(**example)
        assert model_instance

        assert model_instance.topic_name()


def test_task_state_from_worker(mocker: MockerFixture):
    mock_get_worker = mocker.patch(
        "dask_task_models_library.container_tasks.events.get_worker", autospec=True
    )
    fake_job_id = "some_fake_job_id"
    mock_get_worker.return_value.get_current_task.return_value = fake_job_id
    event = TaskStateEvent.from_dask_worker(
        RunningState.FAILED, msg="some test message"
    )
    assert event.job_id == fake_job_id
    assert event.state == RunningState.FAILED
    assert event.msg == "some test message"
