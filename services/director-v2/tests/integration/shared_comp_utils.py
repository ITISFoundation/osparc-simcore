import json
from typing import List
from uuid import UUID

from models_library.projects import ProjectAtDB
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from pydantic.networks import AnyHttpUrl
from pydantic.types import PositiveInt
from requests.models import Response
from simcore_service_director_v2.models.schemas.comp_tasks import ComputationTaskOut
from starlette import status
from starlette.testclient import TestClient
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random

COMPUTATION_URL: str = "v2/computations"


def create_pipeline(
    client: TestClient,
    *,
    project: ProjectAtDB,
    user_id: PositiveInt,
    start_pipeline: bool,
    expected_response_status_code: int,
    **kwargs,
) -> Response:
    response = client.post(
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


def assert_computation_task_out_obj(
    client: TestClient,
    task_out: ComputationTaskOut,
    *,
    project: ProjectAtDB,
    exp_task_state: RunningState,
    exp_pipeline_details: PipelineDetails,
):
    assert task_out.id == project.uuid
    assert task_out.state == exp_task_state
    assert task_out.url == f"{client.base_url}/v2/computations/{project.uuid}"
    assert task_out.stop_url == (
        f"{client.base_url}/v2/computations/{project.uuid}:stop"
        if exp_task_state in [RunningState.PUBLISHED, RunningState.PENDING]
        else None
    )
    # check pipeline details contents
    assert task_out.pipeline_details.dict() == exp_pipeline_details.dict()


async def assert_pipeline_status(
    client: TestClient,
    url: AnyHttpUrl,
    user_id: PositiveInt,
    project_uuid: UUID,
    wait_for_states: List[RunningState] = None,
) -> ComputationTaskOut:
    if not wait_for_states:
        wait_for_states = [
            RunningState.SUCCESS,
            RunningState.FAILED,
            RunningState.ABORTED,
        ]

    MAX_TIMEOUT_S = 60

    async def check_pipeline_state() -> ComputationTaskOut:
        response = client.get(url, params={"user_id": user_id})
        assert (
            response.status_code == status.HTTP_202_ACCEPTED
        ), f"response code is {response.status_code}, error: {response.text}"
        task_out = ComputationTaskOut.parse_obj(response.json())
        assert task_out.id == project_uuid
        assert task_out.url == f"{client.base_url}/v2/computations/{project_uuid}"
        print(
            f"Pipeline '{project_uuid}' current state is '{task_out.state}'",
        )
        assert (
            task_out.state in wait_for_states
        ), f"current task state is '{task_out.state}', not in any of {wait_for_states}"
        return task_out

    async for attempt in AsyncRetrying(
        stop=stop_after_delay(MAX_TIMEOUT_S),
        wait=wait_random(0, 2),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            print(
                f"Waiting for pipeline '{project_uuid}' state to be one of: {wait_for_states}, attempt={attempt.retry_state.attempt_number}"
            )
            task_out = await check_pipeline_state()
            print(
                f"Pipeline '{project_uuid}' state succesfuly became '{task_out.state}'\n{json.dumps(attempt.retry_state.retry_object.statistics, indent=2)}"
            )

            return task_out

    # this is only to satisfy pylance
    raise AssertionError("No computation task generated!")
