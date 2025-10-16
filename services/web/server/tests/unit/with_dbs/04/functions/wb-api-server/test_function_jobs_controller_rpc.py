# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=too-many-arguments

import datetime
from collections.abc import Callable
from uuid import uuid4

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from faker import Faker
from models_library.api_schemas_webserver.functions import ProjectFunctionJob
from models_library.functions import (
    Function,
    FunctionClass,
    FunctionJobCollection,
    FunctionJobStatus,
    RegisteredFunctionJob,
    RegisteredFunctionJobPatch,
    RegisteredProjectFunctionJobPatch,
    RegisteredProjectFunctionJobPatchInput,
    RegisteredProjectFunctionJobPatchInputList,
    RegisteredSolverFunctionJobPatch,
    RegisteredSolverFunctionJobPatchInput,
    RegisteredSolverFunctionJobPatchInputList,
    SolverFunctionJob,
)
from models_library.functions_errors import (
    FunctionJobIDNotFoundError,
    FunctionJobPatchModelIncompatibleError,
    FunctionJobReadAccessDeniedError,
    FunctionJobsReadApiAccessDeniedError,
    FunctionJobWriteAccessDeniedError,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from pydantic import TypeAdapter
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.celery.models import TaskKey
from servicelib.rabbitmq.rpc_interfaces.webserver.v1 import WebServerRpcClient

pytest_simcore_core_services_selection = ["rabbit"]


_faker = Faker()


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_register_get_delete_function_job(
    client: TestClient,
    add_user_function_api_access_rights: None,
    webserver_rpc_client: WebServerRpcClient,
    create_fake_function_obj: Callable[[FunctionClass], Function],
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    osparc_product_name: ProductName,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=create_fake_function_obj(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert registered_function.uid is not None

    function_job = ProjectFunctionJob(
        function_uid=registered_function.uid,
        title="Test Function Job",
        description="A test function job",
        project_job_id=uuid4(),
        inputs={"input1": "value1"},
        outputs={"output1": "result1"},
        job_creation_task_id=None,
    )

    # Register the function job
    registered_jobs = await webserver_rpc_client.functions.register_function_job(
        function_jobs=[function_job],
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert len(registered_jobs) == 1
    registered_job = registered_jobs[0]

    # Assert the registered job matches the input job
    assert registered_job.function_uid == function_job.function_uid
    assert registered_job.inputs == function_job.inputs
    assert registered_job.outputs == function_job.outputs
    assert registered_job.created_at - datetime.datetime.now(
        datetime.UTC
    ) < datetime.timedelta(seconds=60)

    # Retrieve the function job using its ID
    retrieved_job = await webserver_rpc_client.functions.get_function_job(
        function_job_id=registered_job.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the retrieved job matches the registered job
    assert retrieved_job.function_uid == registered_job.function_uid
    assert retrieved_job.inputs == registered_job.inputs
    assert retrieved_job.outputs == registered_job.outputs

    # Test denied access for another user
    with pytest.raises(FunctionJobReadAccessDeniedError):
        await webserver_rpc_client.functions.get_function_job(
            function_job_id=registered_job.uid,
            user_id=other_logged_user["id"],
            product_name=osparc_product_name,
        )

    # Test denied access for another product
    with pytest.raises(FunctionJobsReadApiAccessDeniedError):
        await webserver_rpc_client.functions.get_function_job(
            function_job_id=registered_job.uid,
            user_id=other_logged_user["id"],
            product_name="this_is_not_osparc",
        )

    with pytest.raises(FunctionJobWriteAccessDeniedError):
        # Attempt to delete the function job by another user
        await webserver_rpc_client.functions.delete_function_job(
            function_job_id=registered_job.uid,
            user_id=other_logged_user["id"],
            product_name=osparc_product_name,
        )

    # Delete the function job using its ID
    await webserver_rpc_client.functions.delete_function_job(
        function_job_id=registered_job.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Attempt to retrieve the deleted job
    with pytest.raises(FunctionJobIDNotFoundError):
        await webserver_rpc_client.functions.get_function_job(
            function_job_id=registered_job.uid,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_function_job_not_found(
    client: TestClient,
    add_user_function_api_access_rights: None,
    webserver_rpc_client: WebServerRpcClient,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    clean_functions: None,
):
    # Attempt to retrieve a function job that does not exist
    with pytest.raises(FunctionJobIDNotFoundError):
        await webserver_rpc_client.functions.get_function_job(
            function_job_id=uuid4(),
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_function_jobs(
    client: TestClient,
    add_user_function_api_access_rights: None,
    webserver_rpc_client: WebServerRpcClient,
    create_fake_function_obj: Callable[[FunctionClass], Function],
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=create_fake_function_obj(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert registered_function.uid is not None

    function_job = ProjectFunctionJob(
        function_uid=registered_function.uid,
        title="Test Function Job",
        description="A test function job",
        project_job_id=uuid4(),
        inputs={"input1": "value1"},
        outputs={"output1": "result1"},
        job_creation_task_id=None,
    )

    # Register the function job
    registered_jobs = await webserver_rpc_client.functions.register_function_job(
        function_jobs=[function_job],
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert len(registered_jobs) == 1
    registered_job = registered_jobs[0]

    # List function jobs
    jobs, _ = await webserver_rpc_client.functions.list_function_jobs(
        pagination_limit=10,
        pagination_offset=0,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list contains the registered job
    assert len(jobs) > 0
    assert any(j.uid == registered_job.uid for j in jobs)


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_function_jobs_with_status(
    client: TestClient,
    add_user_function_api_access_rights: None,
    webserver_rpc_client: WebServerRpcClient,
    create_fake_function_obj: Callable[[FunctionClass], Function],
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=create_fake_function_obj(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert registered_function.uid is not None

    function_job = ProjectFunctionJob(
        function_uid=registered_function.uid,
        title="Test Function Job",
        description="A test function job",
        project_job_id=uuid4(),
        inputs={"input1": "value1"},
        outputs={"output1": "result1"},
        job_creation_task_id=None,
    )

    # Register the function job
    registered_jobs = await webserver_rpc_client.functions.register_function_job(
        function_jobs=[function_job],
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert len(registered_jobs) == 1
    registered_job = registered_jobs[0]

    # List function jobs
    jobs, _ = await webserver_rpc_client.functions.list_function_jobs_with_status(
        pagination_limit=10,
        pagination_offset=0,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list contains the registered job
    assert len(jobs) > 0
    assert jobs[0].status.status == "created"
    assert any(j.uid == registered_job.uid for j in jobs)


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_list_function_jobs_filtering(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    create_fake_function_obj: Callable[[FunctionClass], Function],
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    add_user_function_api_access_rights: None,
):
    # Register the function first
    first_registered_function = await webserver_rpc_client.functions.register_function(
        function=create_fake_function_obj(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    second_registered_function = await webserver_rpc_client.functions.register_function(
        function=create_fake_function_obj(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    first_registered_function_jobs = []
    second_registered_function_jobs = []
    for i_job in range(6):
        if i_job < 3:
            function_job = ProjectFunctionJob(
                function_uid=first_registered_function.uid,
                title="Test Function Job",
                description="A test function job",
                project_job_id=uuid4(),
                inputs={"input1": "value1"},
                outputs={"output1": "result1"},
                job_creation_task_id=None,
            )
            # Register the function job
            first_registered_function_jobs += (
                await webserver_rpc_client.functions.register_function_job(
                    function_jobs=[function_job],
                    user_id=logged_user["id"],
                    product_name=osparc_product_name,
                )
            )
        else:
            function_job = ProjectFunctionJob(
                function_uid=second_registered_function.uid,
                title="Test Function Job",
                description="A test function job",
                project_job_id=uuid4(),
                inputs={"input1": "value1"},
                outputs={"output1": "result1"},
                job_creation_task_id=None,
            )
            # Register the function job
            second_registered_function_jobs += (
                await webserver_rpc_client.functions.register_function_job(
                    function_jobs=[function_job],
                    user_id=logged_user["id"],
                    product_name=osparc_product_name,
                )
            )

    job_ids = [
        job.uid
        for job in first_registered_function_jobs[1:2]
        + second_registered_function_jobs[0:1]
    ]
    function_job_collection = (
        await webserver_rpc_client.functions.register_function_job_collection(
            function_job_collection=FunctionJobCollection(job_ids=job_ids),
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
    )

    # List function jobs for a specific function ID
    jobs, _ = await webserver_rpc_client.functions.list_function_jobs(
        pagination_limit=10,
        pagination_offset=0,
        filter_by_function_id=first_registered_function.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list contains the registered job
    assert len(jobs) == 3
    assert all(j.function_uid == first_registered_function.uid for j in jobs)

    # List function jobs for a specific function job IDs
    jobs, _ = await webserver_rpc_client.functions.list_function_jobs(
        pagination_limit=10,
        pagination_offset=0,
        filter_by_function_job_ids=[
            job.uid
            for job in first_registered_function_jobs[0:1]
            + second_registered_function_jobs[1:2]
        ],
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list contains the registered job
    assert len(jobs) == 2
    assert jobs[0].uid == first_registered_function_jobs[0].uid
    assert jobs[1].uid == second_registered_function_jobs[1].uid

    # List function jobs for a specific function job collection
    jobs, _ = await webserver_rpc_client.functions.list_function_jobs(
        pagination_limit=10,
        pagination_offset=0,
        filter_by_function_job_collection_id=function_job_collection.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list contains the registered job
    assert len(jobs) == 2
    assert [job.uid for job in jobs] == job_ids
    assert jobs[0].uid == first_registered_function_jobs[1].uid
    assert jobs[1].uid == second_registered_function_jobs[0].uid

    # List function jobs for a specific function job collection and function job id
    jobs, _ = await webserver_rpc_client.functions.list_function_jobs(
        pagination_limit=10,
        pagination_offset=0,
        filter_by_function_job_collection_id=function_job_collection.uid,
        filter_by_function_job_ids=[first_registered_function_jobs[1].uid],
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the list contains the registered job
    assert len(jobs) == 1
    assert jobs[0].uid == first_registered_function_jobs[1].uid


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_find_cached_function_jobs(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    add_user_function_api_access_rights: None,
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    create_fake_function_obj: Callable[[FunctionClass], Function],
    clean_functions: None,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=create_fake_function_obj(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    registered_function_jobs = []
    for value in range(5):
        function_job = ProjectFunctionJob(
            function_uid=registered_function.uid,
            title="Test Function Job",
            description="A test function job",
            project_job_id=uuid4(),
            inputs={"input1": value if value < 4 else 1},
            outputs={"output1": "result1"},
            job_creation_task_id=None,
        )

        # Register the function job
        registered_jobs = await webserver_rpc_client.functions.register_function_job(
            function_jobs=[function_job],
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
        registered_function_jobs += registered_jobs

    # Find cached function jobs
    cached_jobs = await webserver_rpc_client.functions.find_cached_function_jobs(
        function_id=registered_function.uid,
        inputs=[{"input1": 1}, {"input1": 10}],
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the cached jobs contain the registered job
    assert cached_jobs is not None
    assert len(cached_jobs) == 2
    job0 = cached_jobs[0]
    assert job0 is not None
    assert job0.inputs == {"input1": 1}
    assert cached_jobs[1] is None

    cached_jobs = await webserver_rpc_client.functions.find_cached_function_jobs(
        function_id=registered_function.uid,
        inputs=[{"input1": 1}, {"input1": 10}],
        user_id=other_logged_user["id"],
        product_name=osparc_product_name,
    )

    # Assert the cached jobs does not contain the registered job for the other user
    assert len(cached_jobs) == 2
    assert all(elm is None for elm in cached_jobs)


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_find_cached_function_jobs_with_status(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    add_user_function_api_access_rights: None,
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    create_fake_function_obj: Callable[[FunctionClass], Function],
    clean_functions: None,
):
    # Register the function first
    job_statuses = [
        FunctionJobStatus(status="RUNNING"),
        FunctionJobStatus(status="FAILED"),
    ]
    registered_function = await webserver_rpc_client.functions.register_function(
        function=create_fake_function_obj(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    input_ = {"input1": 1.0}

    for status in job_statuses:
        function_job = ProjectFunctionJob(
            function_uid=registered_function.uid,
            title="Test Function Job",
            description="A test function job",
            project_job_id=uuid4(),
            inputs=input_,
            outputs={"output1": "result1"},
            job_creation_task_id=None,
        )

        # Register the function job
        registered_jobs = await webserver_rpc_client.functions.register_function_job(
            function_jobs=[function_job],
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )
        assert len(registered_jobs) == 1
        registered_job = registered_jobs[0]
        await webserver_rpc_client.functions.update_function_job_status(
            user_id=logged_user["id"],
            product_name=osparc_product_name,
            function_job_id=registered_job.uid,
            job_status=status,
        )

    status = job_statuses[0]
    cached_jobs = await webserver_rpc_client.functions.find_cached_function_jobs(
        function_id=registered_function.uid,
        product_name=osparc_product_name,
        user_id=logged_user["id"],
        inputs=[input_],
        status_filter=[status],
    )
    assert len(cached_jobs) == 1
    cached_job = cached_jobs[0]
    assert cached_job is not None
    assert cached_job.inputs == input_
    cached_job_status = await webserver_rpc_client.functions.get_function_job_status(
        product_name=osparc_product_name,
        function_job_id=cached_job.uid,
        user_id=logged_user["id"],
    )
    assert status == cached_job_status


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
@pytest.mark.parametrize(
    "function_job, patch",
    [
        (
            ProjectFunctionJob(
                function_uid=_faker.uuid4(),
                title="Test Function Job",
                description="A test function job",
                project_job_id=None,
                inputs=None,
                outputs=None,
                job_creation_task_id=None,
            ),
            RegisteredProjectFunctionJobPatch(
                title=_faker.word(),
                description=_faker.sentence(),
                project_job_id=ProjectID(_faker.uuid4()),
                job_creation_task_id=TaskKey(_faker.uuid4()),
                inputs={"input1": _faker.pyint(min_value=0, max_value=1000)},
                outputs={"output1": _faker.word()},
            ),
        ),
        (
            SolverFunctionJob(
                function_uid=_faker.uuid4(),
                title="Test Function Job",
                description="A test function job",
                inputs=None,
                outputs=None,
                job_creation_task_id=None,
                solver_job_id=None,
            ),
            RegisteredSolverFunctionJobPatch(
                title=_faker.word(),
                description=_faker.sentence(),
                job_creation_task_id=TaskKey(_faker.uuid4()),
                inputs={"input1": _faker.pyint(min_value=0, max_value=1000)},
                outputs={"output1": _faker.word()},
                solver_job_id=_faker.uuid4(),
            ),
        ),
    ],
)
async def test_patch_registered_function_jobs(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    add_user_function_api_access_rights: None,
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    create_fake_function_obj: Callable[[FunctionClass], Function],
    clean_functions: None,
    function_job: RegisteredFunctionJob,
    patch: RegisteredFunctionJobPatch,
):
    function = create_fake_function_obj(function_job.function_class)

    registered_function = await webserver_rpc_client.functions.register_function(
        function=function,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    # Register the function job
    function_job.function_uid = registered_function.uid
    registered_jobs = await webserver_rpc_client.functions.register_function_job(
        function_jobs=[function_job],
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert len(registered_jobs) == 1
    registered_job = registered_jobs[0]
    patch_inputs: (
        RegisteredProjectFunctionJobPatchInputList
        | RegisteredSolverFunctionJobPatchInputList
    )
    if function.function_class == FunctionClass.PROJECT:
        assert isinstance(patch, RegisteredProjectFunctionJobPatch)
        patch_inputs = [
            RegisteredProjectFunctionJobPatchInput(uid=registered_job.uid, patch=patch)
        ]
    elif function.function_class == FunctionClass.SOLVER:
        assert isinstance(patch, RegisteredSolverFunctionJobPatch)
        patch_inputs = [
            RegisteredSolverFunctionJobPatchInput(uid=registered_job.uid, patch=patch)
        ]
    else:
        pytest.fail("Unsupported function class")

    registered_jobs = (
        await webserver_rpc_client.functions.patch_registered_function_job(
            user_id=logged_user["id"],
            product_name=osparc_product_name,
            registered_function_job_patch_inputs=patch_inputs,
        )
    )
    assert len(registered_jobs) == 1
    registered_job = registered_jobs[0]
    assert registered_job.title == patch.title
    assert registered_job.description == patch.description
    assert registered_job.inputs == patch.inputs
    assert registered_job.outputs == patch.outputs
    if isinstance(patch, RegisteredProjectFunctionJobPatch):
        assert registered_job.function_class == FunctionClass.PROJECT
        assert registered_job.job_creation_task_id == patch.job_creation_task_id
        assert registered_job.project_job_id == patch.project_job_id
    if isinstance(patch, RegisteredSolverFunctionJobPatch):
        assert registered_job.function_class == FunctionClass.SOLVER
        assert registered_job.job_creation_task_id == patch.job_creation_task_id
        assert registered_job.solver_job_id == patch.solver_job_id


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
@pytest.mark.parametrize(
    "function_job, patch",
    [
        (
            ProjectFunctionJob(
                function_uid=_faker.uuid4(),
                title="Test Function Job",
                description="A test function job",
                project_job_id=None,
                inputs=None,
                outputs=None,
                job_creation_task_id=None,
            ),
            RegisteredSolverFunctionJobPatch(
                title=_faker.word(),
                description=_faker.sentence(),
                job_creation_task_id=TaskKey(_faker.uuid4()),
                inputs={"input1": _faker.pyint(min_value=0, max_value=1000)},
                outputs={"output1": _faker.word()},
                solver_job_id=_faker.uuid4(),
            ),
        ),
    ],
)
async def test_incompatible_patch_model_error(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    add_user_function_api_access_rights: None,
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    create_fake_function_obj: Callable[[FunctionClass], Function],
    clean_functions: None,
    function_job: RegisteredFunctionJob,
    patch: RegisteredProjectFunctionJobPatch | RegisteredSolverFunctionJobPatch,
):
    function = create_fake_function_obj(function_job.function_class)

    registered_function = await webserver_rpc_client.functions.register_function(
        function=function,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    function_job.function_uid = registered_function.uid
    registered_jobs = await webserver_rpc_client.functions.register_function_job(
        function_jobs=[function_job],
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert len(registered_jobs) == 1
    registered_job = registered_jobs[0]
    if function.function_class == FunctionClass.PROJECT:
        assert isinstance(patch, RegisteredSolverFunctionJobPatch)
        patch_input = RegisteredSolverFunctionJobPatchInput(
            uid=registered_job.uid, patch=patch
        )
    elif function.function_class == FunctionClass.SOLVER:
        assert isinstance(patch, RegisteredProjectFunctionJobPatch)
        patch_input = RegisteredProjectFunctionJobPatchInput(
            uid=registered_job.uid, patch=patch
        )
    else:
        pytest.fail("Unsupported function class")
    with pytest.raises(FunctionJobPatchModelIncompatibleError):
        registered_job = (
            await webserver_rpc_client.functions.patch_registered_function_job(
                user_id=logged_user["id"],
                product_name=osparc_product_name,
                registered_function_job_patch_inputs=TypeAdapter(
                    RegisteredSolverFunctionJobPatchInputList
                    | RegisteredSolverFunctionJobPatchInputList
                ).validate_python([patch_input]),
            )
        )


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
@pytest.mark.parametrize(
    "access_by_other_user, check_write_permissions, expected_to_raise",
    [(False, False, None), (True, True, FunctionJobWriteAccessDeniedError)],
)
@pytest.mark.parametrize(
    "status_or_output",
    ["status", "output"],
)
async def test_update_function_job_status_output(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    add_user_function_api_access_rights: None,
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    create_fake_function_obj: Callable[[FunctionClass], Function],
    osparc_product_name: ProductName,
    access_by_other_user: bool,
    check_write_permissions: bool,
    expected_to_raise: type[Exception] | None,
    status_or_output: str,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=create_fake_function_obj(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    function_job = ProjectFunctionJob(
        function_uid=registered_function.uid,
        title="Test Function Job",
        description="A test function job",
        project_job_id=uuid4(),
        inputs={"input1": "value1"},
        outputs={"output1": "result1"},
        job_creation_task_id=None,
    )

    # Register the function job
    registered_jobs = await webserver_rpc_client.functions.register_function_job(
        function_jobs=[function_job],
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert len(registered_jobs) == 1
    registered_job = registered_jobs[0]

    old_job_status = await webserver_rpc_client.functions.get_function_job_status(
        function_job_id=registered_job.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert old_job_status.status == "created"

    await webserver_rpc_client.functions.set_group_permissions(
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        object_type="function_job",
        object_ids=[registered_job.uid],
        permission_group_id=int(other_logged_user["primary_gid"]),
        read=True,
    )

    async def update_job_status_or_output(new_status, new_outputs):
        if status_or_output == "status":
            return await webserver_rpc_client.functions.update_function_job_status(
                function_job_id=registered_job.uid,
                user_id=(
                    other_logged_user["id"]
                    if access_by_other_user
                    else logged_user["id"]
                ),
                product_name=osparc_product_name,
                job_status=new_status,
                check_write_permissions=check_write_permissions,
            )
        return await webserver_rpc_client.functions.update_function_job_outputs(
            function_job_id=registered_job.uid,
            user_id=(
                other_logged_user["id"] if access_by_other_user else logged_user["id"]
            ),
            product_name=osparc_product_name,
            outputs=new_outputs,
            check_write_permissions=check_write_permissions,
        )

    # Update the function job status
    new_status = FunctionJobStatus(status="COMPLETED")
    new_outputs = {"output1": "new_result1", "output2": "new_result2"}
    if expected_to_raise:
        with pytest.raises(expected_to_raise):
            await update_job_status_or_output(new_status, new_outputs)
        return

    return_value = await update_job_status_or_output(new_status, new_outputs)
    if status_or_output == "status":
        assert return_value == new_status
    else:
        assert return_value == new_outputs


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_update_function_job_outputs(
    client: TestClient,
    webserver_rpc_client: WebServerRpcClient,
    add_user_function_api_access_rights: None,
    logged_user: UserInfoDict,
    create_fake_function_obj: Callable[[FunctionClass], Function],
    osparc_product_name: ProductName,
):
    # Register the function first
    registered_function = await webserver_rpc_client.functions.register_function(
        function=create_fake_function_obj(FunctionClass.PROJECT),
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    function_job = ProjectFunctionJob(
        function_uid=registered_function.uid,
        title="Test Function Job",
        description="A test function job",
        project_job_id=uuid4(),
        inputs={"input1": "value1"},
        outputs=None,
        job_creation_task_id=None,
    )

    # Register the function job
    registered_jobs = await webserver_rpc_client.functions.register_function_job(
        function_jobs=[function_job],
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    assert len(registered_jobs) == 1
    registered_job = registered_jobs[0]

    received_outputs = await webserver_rpc_client.functions.get_function_job_outputs(
        function_job_id=registered_job.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    assert received_outputs is None

    new_outputs = {"output1": "new_result1", "output2": "new_result2"}

    # Update the function job outputs
    updated_outputs = await webserver_rpc_client.functions.update_function_job_outputs(
        function_job_id=registered_job.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        outputs=new_outputs,
    )

    # Assert the updated outputs match the new outputs
    assert updated_outputs == new_outputs

    # Update the function job outputs
    received_outputs = await webserver_rpc_client.functions.get_function_job_outputs(
        function_job_id=registered_job.uid,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )

    assert received_outputs == new_outputs
