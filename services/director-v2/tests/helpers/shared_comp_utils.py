import json
import time
from uuid import UUID

import httpx
from models_library.api_schemas_directorv2.comp_tasks import ComputationGet
from models_library.clusters import ClusterID
from models_library.projects import ProjectAtDB
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic import PositiveInt
from pydantic.networks import AnyHttpUrl
from pytest_simcore.helpers.constants import MINUTE
from starlette import status
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


async def assert_computation_task_out_obj(
    task_out: ComputationGet,
    *,
    project: ProjectAtDB,
    exp_task_state: RunningState,
    exp_pipeline_details: PipelineDetails,
    iteration: PositiveInt | None,
    cluster_id: ClusterID | None,
):
    assert task_out.id == project.uuid
    assert task_out.state == exp_task_state
    assert task_out.url.path == f"/v2/computations/{project.uuid}"
    if exp_task_state in [
        RunningState.PUBLISHED,
        RunningState.PENDING,
        RunningState.STARTED,
    ]:
        assert task_out.stop_url
        assert task_out.stop_url.path == f"/v2/computations/{project.uuid}:stop"
    else:
        assert task_out.stop_url is None
    assert task_out.iteration == iteration
    assert task_out.cluster_id == cluster_id
    # check pipeline details contents
    received_task_out_pipeline = task_out.pipeline_details.model_dump()
    expected_task_out_pipeline = exp_pipeline_details.model_dump()
    assert received_task_out_pipeline == expected_task_out_pipeline


async def assert_and_wait_for_pipeline_status(
    client: httpx.AsyncClient,
    url: AnyHttpUrl,
    user_id: UserID,
    project_uuid: UUID,
    wait_for_states: list[RunningState] | None = None,
) -> ComputationGet:
    if not wait_for_states:
        wait_for_states = [
            RunningState.SUCCESS,
            RunningState.FAILED,
            RunningState.ABORTED,
        ]
    MAX_TIMEOUT_S = 5 * MINUTE

    async def check_pipeline_state() -> ComputationGet:
        response = await client.get(f"{url}", params={"user_id": user_id})
        assert (
            response.status_code == status.HTTP_200_OK
        ), f"response code is {response.status_code}, error: {response.text}"
        task_out = ComputationGet.model_validate(response.json())
        assert task_out.id == project_uuid
        assert task_out.url.path == f"/v2/computations/{project_uuid}"
        print(
            f"Pipeline '{project_uuid=}' current task out is '{task_out=}'",
        )
        assert wait_for_states
        assert (
            task_out.state in wait_for_states
        ), f"current task state is '{task_out.state}', not in any of {wait_for_states}"
        return task_out

    start = time.monotonic()
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(MAX_TIMEOUT_S),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        elapsed_s = time.monotonic() - start
        with attempt:
            print(
                f"Waiting for pipeline '{project_uuid=}' state to be one of: {wait_for_states=}, attempt={attempt.retry_state.attempt_number}, time={elapsed_s}s"
            )
            task_out = await check_pipeline_state()
            print(
                f"Pipeline '{project_uuid=}' state succesfuly became '{task_out.state}'\n{json.dumps(attempt.retry_state.retry_object.statistics, indent=2)}, time={elapsed_s}s"
            )

            return task_out

    # this is only to satisfy pylance
    msg = "No computation task generated!"
    raise AssertionError(msg)
