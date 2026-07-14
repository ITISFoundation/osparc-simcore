# pylint: disable=redefined-outer-name

import asyncio
import datetime
from uuid import uuid4

import pytest
from faker import Faker
from models_library.api_schemas_webserver.functions import (
    FunctionClass,
    JSONFunctionInputSchema,
    JSONFunctionOutputSchema,
    RegisteredProjectFunction,
)
from models_library.functions import RegisteredFunction
from models_library.products import ProductName
from models_library.users import UserID
from pytest_mock import MockerFixture
from simcore_service_api_server._service_function_jobs import FunctionJobService, _compute_start_jitter_seconds
from simcore_service_api_server._service_functions import FunctionService
from simcore_service_api_server._service_jobs import JobService
from simcore_service_api_server.models.api_resources import JobLinks
from simcore_service_api_server.models.domain.functions import PreRegisteredFunctionJobData
from simcore_service_api_server.models.schemas.jobs import JobInputs
from simcore_service_api_server.services_http.webserver import AuthSession
from simcore_service_api_server.services_rpc.storage import StorageService
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient

_faker = Faker()


@pytest.fixture
def registered_project_function() -> RegisteredFunction:
    return RegisteredProjectFunction(
        title="test_function",
        function_class=FunctionClass.PROJECT,
        description="A test function",
        input_schema=JSONFunctionInputSchema(
            schema_content={
                "type": "object",
                "properties": {"input1": {"type": "integer"}},
            }
        ),
        output_schema=JSONFunctionOutputSchema(
            schema_content={
                "type": "object",
                "properties": {"output1": {"type": "string"}},
            }
        ),
        default_inputs=None,
        project_id=uuid4(),
        uid=uuid4(),
        created_at=datetime.datetime.now(datetime.UTC),
        modified_at=datetime.datetime.now(datetime.UTC),
    )


@pytest.fixture
def function_job_service(
    mocker: MockerFixture,
    user_id: UserID,
    product_name: ProductName,
) -> FunctionJobService:
    return FunctionJobService(
        user_id=user_id,
        product_name=product_name,
        _web_rpc_client=mocker.AsyncMock(spec=WbApiRpcClient),
        _storage_client=mocker.AsyncMock(spec=StorageService),
        _job_service=mocker.AsyncMock(spec=JobService),
        _function_service=mocker.AsyncMock(spec=FunctionService),
        _webserver_api=mocker.AsyncMock(spec=AuthSession),
    )


async def test_batch_pre_register_function_jobs_with_empty_list(
    function_job_service: FunctionJobService,
    registered_project_function: RegisteredFunction,
):
    result = await function_job_service.batch_pre_register_function_jobs(
        function=registered_project_function,
        job_input_list=[],
    )

    assert result == []


async def test_run_function_start_is_jittered(
    function_job_service: FunctionJobService,
    registered_project_function: RegisteredFunction,
    fake_job_links: JobLinks,
    mocker: MockerFixture,
):
    """Concurrently calling run_function for a burst of jobs (e.g. a map/sweep)
    must not trigger the actual computation start (start_study_job) for all of
    them at the exact same instant: the pre-start jitter should spread out when
    each one actually starts, to avoid overloading director-v2/dask with a burst
    of simultaneous submissions.
    """
    num_jobs = 40

    fake_job = mocker.Mock(id=uuid4())
    function_job_service._job_service.create_studies_job = mocker.AsyncMock(return_value=fake_job)  # noqa: SLF001
    function_job_service._web_rpc_client.patch_registered_function_job = mocker.AsyncMock(  # noqa: SLF001
        return_value=mocker.Mock()
    )

    start_times: list[float] = []

    async def _record_start_time(*args, **kwargs) -> None:
        start_times.append(asyncio.get_running_loop().time())

    function_job_service._job_service.start_study_job = mocker.AsyncMock(  # noqa: SLF001
        side_effect=_record_start_time
    )

    pre_registered_jobs = [
        PreRegisteredFunctionJobData(function_job_id=uuid4(), job_inputs=JobInputs(values={})) for _ in range(num_jobs)
    ]

    def _run_function(data: PreRegisteredFunctionJobData):
        return function_job_service.run_function(
            function=registered_project_function,
            pre_registered_function_job_data=data,
            pricing_spec=None,
            job_links=fake_job_links,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            batch_size=num_jobs,
        )

    await asyncio.gather(*map(_run_function, pre_registered_jobs))

    assert len(start_times) == num_jobs
    spread = max(start_times) - min(start_times)
    expected_jitter_max = _compute_start_jitter_seconds(batch_size=num_jobs)
    assert spread > expected_jitter_max * 0.3, (
        f"Expected start_study_job calls to be spread out by jitter, but spread was only {spread}s "
        f"(jitter max is {expected_jitter_max}s)"
    )


async def test_run_function_isolated_call_has_no_jitter(
    function_job_service: FunctionJobService,
    registered_project_function: RegisteredFunction,
    fake_job_links: JobLinks,
    mocker: MockerFixture,
):
    """An isolated run_function call (batch_size=1, the default) must not incur
    any jitter delay, since there is no burst of sibling jobs to desynchronize.
    """
    fake_job = mocker.Mock(id=uuid4())
    function_job_service._job_service.create_studies_job = mocker.AsyncMock(return_value=fake_job)  # noqa: SLF001
    function_job_service._web_rpc_client.patch_registered_function_job = mocker.AsyncMock(  # noqa: SLF001
        return_value=mocker.Mock()
    )
    function_job_service._job_service.start_study_job = mocker.AsyncMock()  # noqa: SLF001

    data = PreRegisteredFunctionJobData(function_job_id=uuid4(), job_inputs=JobInputs(values={}))

    start = asyncio.get_running_loop().time()
    await function_job_service.run_function(
        function=registered_project_function,
        pre_registered_function_job_data=data,
        pricing_spec=None,
        job_links=fake_job_links,
        x_simcore_parent_project_uuid=None,
        x_simcore_parent_node_id=None,
    )
    elapsed = asyncio.get_running_loop().time() - start

    assert elapsed < 0.1
