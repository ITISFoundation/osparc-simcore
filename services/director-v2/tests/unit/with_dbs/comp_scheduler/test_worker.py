# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module
# pylint: disable=too-many-statements

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from unittest import mock

import pytest
from _helpers import PublishedProject
from fastapi import FastAPI
from models_library.computations import CollectionRunID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from simcore_service_director_v2.models.comp_runs import RunMetadataDict
from simcore_service_director_v2.modules.comp_scheduler._manager import run_new_pipeline
from simcore_service_director_v2.modules.comp_scheduler._models import (
    SchedulePipelineRabbitMessage,
)
from simcore_service_director_v2.modules.comp_scheduler._worker import (
    _get_scheduler_worker,
)

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = ["adminer"]


async def test_worker_starts_and_stops(initialized_app: FastAPI):
    assert _get_scheduler_worker(initialized_app) is not None


@pytest.fixture
def mock_schedule_pipeline(mocker: MockerFixture) -> mock.Mock:
    mock_scheduler_worker = mock.Mock()
    mock_scheduler_worker.schedule_pipeline = mocker.AsyncMock(return_value=True)
    return mock_scheduler_worker


@pytest.fixture
def mocked_get_scheduler_worker(
    mocker: MockerFixture,
    mock_schedule_pipeline: mock.Mock,
) -> mock.Mock:
    # Mock `_get_scheduler_worker` to return our mock scheduler
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._worker._get_scheduler_worker",
        return_value=mock_schedule_pipeline,
    )


async def test_worker_properly_autocalls_scheduler_api(
    with_disabled_auto_scheduling: mock.Mock,
    initialized_app: FastAPI,
    mocked_get_scheduler_worker: mock.Mock,
    published_project: PublishedProject,
    run_metadata: RunMetadataDict,
    fake_collection_run_id: CollectionRunID,
):
    assert published_project.project.prj_owner
    await run_new_pipeline(
        initialized_app,
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        run_metadata=run_metadata,
        use_on_demand_clusters=False,
        collection_run_id=fake_collection_run_id,
    )
    mocked_get_scheduler_worker.assert_called_once_with(initialized_app)
    mocked_get_scheduler_worker.return_value.apply.assert_called_once_with(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        iteration=1,
    )


@pytest.fixture
async def mocked_scheduler_api(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch("simcore_service_director_v2.modules.comp_scheduler._scheduler_base.BaseCompScheduler.apply")


@pytest.fixture
def with_scheduling_concurrency(
    mock_env: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, scheduling_concurrency: int
) -> EnvVarsDict:
    return mock_env | setenvs_from_dict(
        monkeypatch,
        {"COMPUTATIONAL_BACKEND_SCHEDULING_CONCURRENCY": f"{scheduling_concurrency}"},
    )


@pytest.mark.parametrize("scheduling_concurrency", [1, 50, 100])
@pytest.mark.parametrize("queue_name", [SchedulePipelineRabbitMessage.get_channel_name()])
async def test_worker_scheduling_parallelism(
    rabbit_service: RabbitSettings,
    ensure_parametrized_queue_is_empty: None,
    scheduling_concurrency: int,
    with_scheduling_concurrency: EnvVarsDict,
    with_disabled_auto_scheduling: mock.Mock,
    mocked_scheduler_api: mock.Mock,
    initialized_app: FastAPI,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    run_metadata: RunMetadataDict,
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    with_disabled_auto_scheduling.assert_called_once()

    # NOTE: rendezvous barrier instead of a fixed sleep: each call blocks until
    # `scheduling_concurrency` calls are simultaneously in-flight, which deterministically
    # proves they run concurrently (not queued up one at a time) and, since it resolves as
    # soon as that is true, is neither slower nor flakier than reality allows - unlike a
    # fixed sleep, it does not need to guess a "long enough" duration.
    # NOTE: this queue is durable and shared by the whole comp_scheduler test suite (other
    # tests in test_manager.py/test_scheduler_dask.py also publish real messages on it), so a
    # stray message from a completely unrelated test can occasionally be delivered to this
    # test's own consumer(s). We only track/synchronize on calls for the (user_id, project_id)
    # pairs *we* actually scheduled below; anything else is such a stray and is simply ignored.
    our_project_keys: set[tuple[int, str]] = set()
    concurrent_calls = 0
    peak_concurrent_calls = 0
    completed_calls = 0
    all_running_concurrently = asyncio.Event()
    all_calls_returned = asyncio.Event()

    async def _side_effect(*args, **kwargs):
        nonlocal concurrent_calls, peak_concurrent_calls, completed_calls
        if (kwargs.get("user_id"), f"{kwargs.get('project_id')}") not in our_project_keys:
            return
        concurrent_calls += 1
        peak_concurrent_calls = max(peak_concurrent_calls, concurrent_calls)
        if peak_concurrent_calls == scheduling_concurrency:
            all_running_concurrently.set()
        await all_running_concurrently.wait()
        concurrent_calls -= 1
        completed_calls += 1
        if completed_calls == scheduling_concurrency:
            all_calls_returned.set()

    mocked_scheduler_api.side_effect = _side_effect

    async def _project_pipeline_creation_workflow() -> None:
        published_project = await publish_project()
        assert published_project.project.prj_owner
        our_project_keys.add((published_project.project.prj_owner, f"{published_project.project.uuid}"))
        await run_new_pipeline(
            initialized_app,
            user_id=published_project.project.prj_owner,
            project_id=published_project.project.uuid,
            run_metadata=run_metadata,
            use_on_demand_clusters=False,
            collection_run_id=fake_collection_run_id,
        )

    # whatever scheduling concurrency we call in here, we shall always see the same number of calls to the scheduler
    await asyncio.gather(*(_project_pipeline_creation_workflow() for _ in range(scheduling_concurrency)))

    # NOTE: the messages are only acked once the handler (i.e. `apply`, including its own
    # lock-release cleanup) fully returns. If the test returned earlier, the app/rabbitmq
    # connection would be torn down while those messages are still un-acked, which makes the
    # broker requeue them. Since the queue name is shared across all the parametrized runs of
    # this test, that leftover message would then be redelivered to (and counted by) the *next*
    # parametrized test, causing flaky off-by-one failures there. So we wait for every call to
    # have actually returned (not just started), which also fails fast instead of hanging if the
    # worker is not actually running the calls concurrently.
    await asyncio.wait_for(all_calls_returned.wait(), timeout=10)
    # small grace period for `apply`'s own post-return cleanup (lock release, message ack) to
    # flush, so a late/duplicate call would still be observed by the assertions below
    await asyncio.sleep(0.5)
    assert completed_calls == scheduling_concurrency
    assert peak_concurrent_calls == scheduling_concurrency
