import json
import time
from typing import List, Optional
from uuid import UUID

import httpx
from models_library.clusters import ClusterID
from models_library.projects import ProjectAtDB
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic import PositiveInt
from pydantic.networks import AnyHttpUrl
from pytest_simcore.helpers.constants import MINUTE
from simcore_service_director_v2.models.schemas.comp_tasks import ComputationGet
from starlette import status
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

COMPUTATION_URL: str = "v2/computations"


async def create_pipeline(
    client: httpx.AsyncClient,
    *,
    project: ProjectAtDB,
    user_id: UserID,
    start_pipeline: bool,
    expected_response_status_code: int,
    **kwargs,
) -> httpx.Response:
    response = await client.post(
        COMPUTATION_URL,
        json={
            "user_id": user_id,
            "project_id": str(project.uuid),
            "start_pipeline": start_pipeline,
            **kwargs,
        },
    )
    assert (
        response.status_code == expected_response_status_code
    ), f"response code is {response.status_code}, error: {response.text}"
    return response


async def assert_computation_task_out_obj(
    task_out: ComputationGet,
    *,
    project: ProjectAtDB,
    exp_task_state: RunningState,
    exp_pipeline_details: PipelineDetails,
    iteration: Optional[PositiveInt],
    cluster_id: Optional[ClusterID],
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
    assert task_out.pipeline_details.dict() == exp_pipeline_details.dict()


async def assert_and_wait_for_pipeline_status(
    client: httpx.AsyncClient,
    url: AnyHttpUrl,
    user_id: UserID,
    project_uuid: UUID,
    wait_for_states: Optional[List[RunningState]] = None,
) -> ComputationGet:
    if not wait_for_states:
        wait_for_states = [
            RunningState.SUCCESS,
            RunningState.FAILED,
            RunningState.ABORTED,
        ]
    MAX_TIMEOUT_S = 5 * MINUTE

    async def check_pipeline_state() -> ComputationGet:
        response = await client.get(url, params={"user_id": user_id})
        assert (
            response.status_code == status.HTTP_200_OK
        ), f"response code is {response.status_code}, error: {response.text}"
        task_out = ComputationGet.parse_obj(response.json())
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
    raise AssertionError("No computation task generated!")
