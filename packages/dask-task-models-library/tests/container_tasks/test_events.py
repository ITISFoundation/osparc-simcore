# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments


import pytest
from dask_task_models_library.container_tasks.events import (
    BaseTaskEvent,
    TaskProgressEvent,
)
from dask_task_models_library.container_tasks.protocol import TaskOwner
from faker import Faker
from pytest_mock.plugin import MockerFixture


def test_task_event_abstract():
    with pytest.raises(TypeError):
        # pylint: disable=abstract-class-instantiated
        BaseTaskEvent(job_id="some_fake")  # type: ignore


@pytest.mark.parametrize("model_cls", [TaskProgressEvent])
def test_events_models_examples(model_cls):
    examples = model_cls.model_config["json_schema_extra"]["examples"]

    for index, example in enumerate(examples):
        print(f"{index:-^10}:\n", example)

        model_instance = model_cls(**example)
        assert model_instance

        assert model_instance.topic_name()


@pytest.fixture(params=["string", "bytes"])
def job_id(faker: Faker, request: pytest.FixtureRequest) -> str | bytes:
    return faker.pystr() if request.param == "string" else faker.pystr().encode()


@pytest.fixture()
def mocked_dask_worker_job_id(
    mocker: MockerFixture, job_id: str | bytes
) -> str | bytes:
    mock_get_worker = mocker.patch(
        "dask_task_models_library.container_tasks.events.get_worker", autospec=True
    )
    mock_get_worker.return_value.get_current_task.return_value = job_id
    return job_id


@pytest.fixture(params=TaskOwner.model_json_schema()["examples"])
def task_owner(request: pytest.FixtureRequest) -> TaskOwner:
    return TaskOwner(**request.param)


def test_task_progress_from_worker(
    mocked_dask_worker_job_id: str | bytes, task_owner: TaskOwner
):
    event = TaskProgressEvent.from_dask_worker(0.7, task_owner=task_owner)

    assert (
        event.job_id == mocked_dask_worker_job_id.decode()
        if isinstance(mocked_dask_worker_job_id, bytes)
        else mocked_dask_worker_job_id
    )
    assert event.progress == 0.7


@pytest.mark.parametrize(
    "progress_value, expected_progress", [(1.5, 1), (-0.5, 0), (0.75, 0.75)]
)
def test_task_progress_progress_value_is_capped_between_0_and_1(
    mocked_dask_worker_job_id: str | bytes,
    task_owner: TaskOwner,
    progress_value: float,
    expected_progress: float,
):
    event = TaskProgressEvent(
        job_id=(
            mocked_dask_worker_job_id.decode()
            if isinstance(mocked_dask_worker_job_id, bytes)
            else mocked_dask_worker_job_id
        ),
        task_owner=task_owner,
        progress=progress_value,
    )
    assert event
    assert event.progress == expected_progress
