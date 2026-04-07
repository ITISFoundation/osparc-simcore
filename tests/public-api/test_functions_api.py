# pylint: disable=no-self-use
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""
E2E tests for the Functions API.
"""

import contextlib
import logging
import os
import time
import uuid
from collections.abc import Iterator

import osparc_client
import pytest
from pytest_simcore.helpers.typing_public_api import RegisteredUserDict, ServiceInfoDict, ServiceNameStr

_logger = logging.getLogger(__name__)

_MINUTE: int = 60  # in secs
_POLL_INTERVAL: float = 1.0  # secs between status polls
_MAX_JOB_WAIT: int = 5 * _MINUTE  # max time to wait for a job to finish


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _api_client(
    registered_user: RegisteredUserDict,
) -> Iterator[osparc_client.ApiClient]:
    cfg = osparc_client.Configuration(
        host=os.environ.get("OSPARC_API_URL", "http://127.0.0.1:8006"),
        username=registered_user["api_key"],
        password=registered_user["api_secret"],
    )
    with osparc_client.ApiClient(cfg) as client:
        yield client


@pytest.fixture(scope="module")
def functions_api(
    _api_client: osparc_client.ApiClient,
    services_registry: dict[ServiceNameStr, ServiceInfoDict],
) -> osparc_client.FunctionsApi:
    return osparc_client.FunctionsApi(_api_client)


@pytest.fixture(scope="module")
def function_jobs_api(
    _api_client: osparc_client.ApiClient,
) -> osparc_client.FunctionJobsApi:
    return osparc_client.FunctionJobsApi(_api_client)


@pytest.fixture(scope="module")
def function_job_collections_api(
    _api_client: osparc_client.ApiClient,
) -> osparc_client.FunctionJobCollectionsApi:
    return osparc_client.FunctionJobCollectionsApi(_api_client)


@pytest.fixture(scope="module")
def files_api(
    _api_client: osparc_client.ApiClient,
) -> osparc_client.FilesApi:
    return osparc_client.FilesApi(_api_client)


@pytest.fixture(scope="module")
def sleeper_key_and_version(
    services_registry: dict[ServiceNameStr, ServiceInfoDict],
) -> tuple[str, str]:
    sleeper = services_registry["sleeper_service"]
    return sleeper["name"], sleeper["version"]


def _build_solver_function(
    solver_key: str,
    solver_version: str,
    *,
    title: str = "test-solver-function",
    description: str = "A test solver function",
    default_inputs: dict | None = None,
) -> osparc_client.Function:
    return osparc_client.Function(
        osparc_client.SolverFunction(
            title=title,
            description=description,
            input_schema=osparc_client.JSONFunctionInputSchema(),
            output_schema=osparc_client.JSONFunctionOutputSchema(),
            solver_key=solver_key,
            solver_version=solver_version,
            default_inputs=default_inputs or {},
        )
    )


_NULL_PARENT_HEADERS: dict[str, str] = {
    "x-simcore-parent-project-uuid": "null",
    "x-simcore-parent-node-id": "null",
}


def _get_function_uid(registered_function) -> str:
    uid = registered_function.actual_instance.uid
    assert uid is not None
    return uid


def _get_job_uid(job_item):
    """Extract uid from a function job, handling nested discriminated unions."""
    obj = job_item
    while hasattr(obj, "actual_instance"):
        obj = obj.actual_instance
    return obj.uid


def _wait_for_job(
    function_jobs_api: osparc_client.FunctionJobsApi,
    job_uid: str,
    *,
    timeout: int = _MAX_JOB_WAIT,
) -> str:
    """Poll job status until it reaches a terminal state. Returns final status string."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status_resp = function_jobs_api.function_job_status(job_uid)
        status = status_resp.status
        if status in ("SUCCESS", "FAILED"):
            return status
        time.sleep(_POLL_INTERVAL)
    msg = f"Job {job_uid} did not finish within {timeout}s"
    raise TimeoutError(msg)


def _delete_function_and_jobs(
    functions_api: osparc_client.FunctionsApi,
    function_jobs_api: osparc_client.FunctionJobsApi,
    function_uid: str,
) -> None:
    """Delete all jobs for a function, then delete the function itself."""
    with contextlib.suppress(osparc_client.ApiException):
        jobs_page = functions_api.list_function_jobs_for_functionid(function_uid)
        for job in jobs_page.items:
            with contextlib.suppress(osparc_client.ApiException):
                function_jobs_api.delete_function_job(job.actual_instance.uid)
    with contextlib.suppress(osparc_client.ApiException):
        functions_api.delete_function(function_uid)


class TestFunctionCRUD:
    """Register, get, list, update, and delete functions."""

    def test_register_solver_function(
        self,
        functions_api: osparc_client.FunctionsApi,
        sleeper_key_and_version: tuple[str, str],
    ):
        solver_key, solver_version = sleeper_key_and_version
        func = _build_solver_function(solver_key, solver_version)
        registered = functions_api.register_function(func.model_dump())

        uid = _get_function_uid(registered)
        assert uid
        assert registered.actual_instance.title == "test-solver-function"
        assert registered.actual_instance.description == "A test solver function"

        # cleanup
        functions_api.delete_function(uid)

    def test_get_function(
        self,
        functions_api: osparc_client.FunctionsApi,
        sleeper_key_and_version: tuple[str, str],
    ):
        solver_key, solver_version = sleeper_key_and_version
        func = _build_solver_function(solver_key, solver_version, title="get-me")
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        fetched = functions_api.get_function(uid)
        assert _get_function_uid(fetched) == uid
        assert fetched.actual_instance.title == "get-me"

        # cleanup
        functions_api.delete_function(uid)

    def test_list_functions(
        self,
        functions_api: osparc_client.FunctionsApi,
        sleeper_key_and_version: tuple[str, str],
    ):
        solver_key, solver_version = sleeper_key_and_version

        # register two functions
        uids = []
        for i in range(2):
            func = _build_solver_function(solver_key, solver_version, title=f"list-test-{i}")
            registered = functions_api.register_function(func.model_dump())
            uids.append(_get_function_uid(registered))

        page = functions_api.list_functions()
        listed_uids = [_get_function_uid(f) for f in page.items]
        for uid in uids:
            assert uid in listed_uids

        # cleanup
        for uid in uids:
            functions_api.delete_function(uid)

    def test_list_functions_pagination(
        self,
        functions_api: osparc_client.FunctionsApi,
        sleeper_key_and_version: tuple[str, str],
    ):
        solver_key, solver_version = sleeper_key_and_version

        uids = []
        for i in range(3):
            func = _build_solver_function(solver_key, solver_version, title=f"page-test-{i}")
            registered = functions_api.register_function(func.model_dump())
            uids.append(_get_function_uid(registered))

        # fetch first page with limit=1
        page1 = functions_api.list_functions(limit=1, offset=0)
        assert len(page1.items) == 1
        assert page1.total >= 3

        # fetch second page
        page2 = functions_api.list_functions(limit=1, offset=1)
        assert len(page2.items) == 1
        assert _get_function_uid(page2.items[0]) != _get_function_uid(page1.items[0])

        # cleanup
        for uid in uids:
            functions_api.delete_function(uid)

    def test_update_function_title(
        self,
        functions_api: osparc_client.FunctionsApi,
        sleeper_key_and_version: tuple[str, str],
    ):
        solver_key, solver_version = sleeper_key_and_version
        func = _build_solver_function(solver_key, solver_version, title="old-title")
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        updated = functions_api.update_function_title(uid, title="new-title")
        assert updated.actual_instance.title == "new-title"

        # verify persistence
        fetched = functions_api.get_function(uid)
        assert fetched.actual_instance.title == "new-title"

        # cleanup
        functions_api.delete_function(uid)

    def test_update_function_description(
        self,
        functions_api: osparc_client.FunctionsApi,
        sleeper_key_and_version: tuple[str, str],
    ):
        solver_key, solver_version = sleeper_key_and_version
        func = _build_solver_function(solver_key, solver_version, description="old-desc")
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        updated = functions_api.update_function_description(uid, description="new-desc")
        assert updated.actual_instance.description == "new-desc"

        # verify persistence
        fetched = functions_api.get_function(uid)
        assert fetched.actual_instance.description == "new-desc"

        # cleanup
        functions_api.delete_function(uid)

    def test_delete_function(
        self,
        functions_api: osparc_client.FunctionsApi,
        sleeper_key_and_version: tuple[str, str],
    ):
        solver_key, solver_version = sleeper_key_and_version
        func = _build_solver_function(solver_key, solver_version, title="to-delete")
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        functions_api.delete_function(uid)

        with pytest.raises(osparc_client.ApiException) as exc_info:
            functions_api.get_function(uid)
        assert exc_info.value.status == 404

    def test_get_nonexistent_function_returns_404(
        self,
        functions_api: osparc_client.FunctionsApi,
    ):
        fake_id = str(uuid.uuid4())
        with pytest.raises(osparc_client.ApiException) as exc_info:
            functions_api.get_function(fake_id)
        assert exc_info.value.status == 404


class TestFunctionSchemas:
    """Get input and output schemas for a registered function."""

    def test_get_input_schema(
        self,
        functions_api: osparc_client.FunctionsApi,
        sleeper_key_and_version: tuple[str, str],
    ):
        solver_key, solver_version = sleeper_key_and_version
        func = _build_solver_function(solver_key, solver_version)
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        schema = functions_api.get_function_inputschema(uid)
        assert schema is not None

        # cleanup
        functions_api.delete_function(uid)

    def test_get_output_schema(
        self,
        functions_api: osparc_client.FunctionsApi,
        sleeper_key_and_version: tuple[str, str],
    ):
        solver_key, solver_version = sleeper_key_and_version
        func = _build_solver_function(solver_key, solver_version)
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        schema = functions_api.get_function_outputschema(uid)
        assert schema is not None

        # cleanup
        functions_api.delete_function(uid)


class TestFunctionInputValidation:
    """Validate function inputs."""

    def test_validate_valid_inputs(
        self,
        functions_api: osparc_client.FunctionsApi,
        sleeper_key_and_version: tuple[str, str],
    ):
        solver_key, solver_version = sleeper_key_and_version
        func = _build_solver_function(solver_key, solver_version)
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        result = functions_api.validate_function_inputs(
            uid, request_body={"input_2": 1, "input_3": False, "input_4": 0}
        )
        assert result is not None

        # cleanup
        functions_api.delete_function(uid)


# ---------------------------------------------------------------------------
# Tests - Run Function & Jobs
# ---------------------------------------------------------------------------


class TestRunFunctionAndJobs:
    """Run a function, inspect job status, retrieve outputs."""

    @pytest.fixture()
    def registered_sleeper_function(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        files_api: osparc_client.FilesApi,
        sleeper_key_and_version: tuple[str, str],
        tmp_path_factory: pytest.TempPathFactory,
    ) -> Iterator[tuple[str, osparc_client.FilesApi]]:
        solver_key, solver_version = sleeper_key_and_version

        # upload an input file
        tmpdir = tmp_path_factory.mktemp("sleeper_input")
        input_path = tmpdir / "single_number.txt"
        input_path.write_text("3")
        input_file = files_api.upload_file(file=str(input_path))
        assert input_file.id

        func = _build_solver_function(
            solver_key,
            solver_version,
            title="sleeper-run-test",
            default_inputs={"input_1": input_file},
        )
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        yield uid, files_api

        # cleanup: delete jobs first, then function
        _delete_function_and_jobs(functions_api, function_jobs_api, uid)
        with contextlib.suppress(osparc_client.ApiException):
            files_api.delete_file(input_file.id)

    def test_run_function_success(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        registered_sleeper_function: tuple[str, osparc_client.FilesApi],
    ):
        function_uid, _files_api = registered_sleeper_function

        job = functions_api.run_function(
            function_id=function_uid,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            _headers=_NULL_PARENT_HEADERS,
            request_body={"input_2": 1, "input_3": False, "input_4": 0},
        )
        job_uid = job.actual_instance.uid
        assert job_uid

        # wait for completion
        final_status = _wait_for_job(function_jobs_api, job_uid)
        assert final_status == "SUCCESS"

        # check outputs
        outputs = function_jobs_api.function_job_outputs(job_uid)
        assert outputs is not None

    def test_run_function_failure(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        registered_sleeper_function: tuple[str, osparc_client.FilesApi],
    ):
        function_uid, _ = registered_sleeper_function

        # input_3=True causes the sleeper to fail
        job = functions_api.run_function(
            function_id=function_uid,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            _headers=_NULL_PARENT_HEADERS,
            request_body={"input_2": 1, "input_3": True, "input_4": 0},
        )
        job_uid = job.actual_instance.uid
        assert job_uid

        final_status = _wait_for_job(function_jobs_api, job_uid)
        assert final_status == "FAILED"

    def test_get_function_job(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        registered_sleeper_function: tuple[str, osparc_client.FilesApi],
    ):
        function_uid, _ = registered_sleeper_function

        job = functions_api.run_function(
            function_id=function_uid,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            _headers=_NULL_PARENT_HEADERS,
            request_body={"input_2": 1, "input_3": False, "input_4": 0},
        )
        job_uid = job.actual_instance.uid

        fetched_job = function_jobs_api.get_function_job(job_uid)
        assert fetched_job.actual_instance.uid == job_uid
        assert fetched_job.actual_instance.function_uid == function_uid

        _wait_for_job(function_jobs_api, job_uid)

    def test_function_job_status_polling(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        registered_sleeper_function: tuple[str, osparc_client.FilesApi],
    ):
        function_uid, _ = registered_sleeper_function

        job = functions_api.run_function(
            function_id=function_uid,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            _headers=_NULL_PARENT_HEADERS,
            request_body={"input_2": 1, "input_3": False, "input_4": 0},
        )
        job_uid = job.actual_instance.uid

        # should be able to poll status immediately
        status_resp = function_jobs_api.function_job_status(job_uid)
        assert status_resp.status in (
            "UNKNOWN",
            "PENDING",
            "PUBLISHED",
            "STARTED",
            "RETRY",
            "SUCCESS",
            "FAILED",
            "JOB_TASK_RUN_STATUS_STARTED",
            "JOB_TASK_RUN_STATUS_PENDING",
        )

        _wait_for_job(function_jobs_api, job_uid)

    def test_delete_function_job(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        registered_sleeper_function: tuple[str, osparc_client.FilesApi],
    ):
        function_uid, _ = registered_sleeper_function

        job = functions_api.run_function(
            function_id=function_uid,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            _headers=_NULL_PARENT_HEADERS,
            request_body={"input_2": 1, "input_3": False, "input_4": 0},
        )
        job_uid = job.actual_instance.uid

        _wait_for_job(function_jobs_api, job_uid)

        function_jobs_api.delete_function_job(job_uid)

        with pytest.raises(osparc_client.ApiException) as exc_info:
            function_jobs_api.get_function_job(job_uid)
        assert exc_info.value.status == 404


class TestListFunctionJobs:
    """List and filter function jobs."""

    def test_list_function_jobs(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        sleeper_key_and_version: tuple[str, str],
        files_api: osparc_client.FilesApi,
        tmp_path_factory: pytest.TempPathFactory,
    ):
        solver_key, solver_version = sleeper_key_and_version

        tmpdir = tmp_path_factory.mktemp("list_jobs_input")
        input_path = tmpdir / "single_number.txt"
        input_path.write_text("3")
        input_file = files_api.upload_file(file=str(input_path))

        func = _build_solver_function(
            solver_key,
            solver_version,
            title="list-jobs-test",
            default_inputs={"input_1": input_file},
        )
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        # run two jobs
        job_uids = []
        for _ in range(2):
            job = functions_api.run_function(
                function_id=uid,
                x_simcore_parent_project_uuid=None,
                x_simcore_parent_node_id=None,
                _headers=_NULL_PARENT_HEADERS,
                request_body={"input_2": 1, "input_3": False, "input_4": 0},
            )
            job_uids.append(job.actual_instance.uid)

        # list all jobs for this function
        all_jobs = function_jobs_api.list_function_jobs(function_id=uid)
        all_job_uids = [_get_job_uid(j) for j in all_jobs.items]
        for jid in job_uids:
            assert jid in all_job_uids

        # wait and cleanup
        for jid in job_uids:
            _wait_for_job(function_jobs_api, jid)

        _delete_function_and_jobs(functions_api, function_jobs_api, uid)
        files_api.delete_file(input_file.id)

    def test_list_function_jobs_for_function(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        sleeper_key_and_version: tuple[str, str],
        files_api: osparc_client.FilesApi,
        tmp_path_factory: pytest.TempPathFactory,
    ):
        solver_key, solver_version = sleeper_key_and_version

        tmpdir = tmp_path_factory.mktemp("list_jobs_for_fn_input")
        input_path = tmpdir / "single_number.txt"
        input_path.write_text("3")
        input_file = files_api.upload_file(file=str(input_path))

        func = _build_solver_function(
            solver_key,
            solver_version,
            title="list-jobs-for-fn",
            default_inputs={"input_1": input_file},
        )
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        job = functions_api.run_function(
            function_id=uid,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            _headers=_NULL_PARENT_HEADERS,
            request_body={"input_2": 1, "input_3": False, "input_4": 0},
        )
        job_uid = job.actual_instance.uid

        # list jobs filtered by function_id
        fn_jobs = functions_api.list_function_jobs_for_functionid(uid)
        fn_job_uids = [_get_job_uid(j) for j in fn_jobs.items]
        assert job_uid in fn_job_uids

        # also verify via function_jobs_api filter
        filtered_jobs = function_jobs_api.list_function_jobs(function_id=uid)
        filtered_uids = [_get_job_uid(j) for j in filtered_jobs.items]
        assert job_uid in filtered_uids

        _wait_for_job(function_jobs_api, job_uid)
        _delete_function_and_jobs(functions_api, function_jobs_api, uid)
        files_api.delete_file(input_file.id)

    def test_list_function_jobs_with_status(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        sleeper_key_and_version: tuple[str, str],
        files_api: osparc_client.FilesApi,
        tmp_path_factory: pytest.TempPathFactory,
    ):
        solver_key, solver_version = sleeper_key_and_version

        tmpdir = tmp_path_factory.mktemp("list_jobs_status_input")
        input_path = tmpdir / "single_number.txt"
        input_path.write_text("3")
        input_file = files_api.upload_file(file=str(input_path))

        func = _build_solver_function(
            solver_key,
            solver_version,
            title="list-jobs-status",
            default_inputs={"input_1": input_file},
        )
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        job = functions_api.run_function(
            function_id=uid,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            _headers=_NULL_PARENT_HEADERS,
            request_body={"input_2": 1, "input_3": False, "input_4": 0},
        )
        job_uid = _get_job_uid(job)

        _wait_for_job(function_jobs_api, job_uid)

        # list with include_status=True
        jobs_with_status = function_jobs_api.list_function_jobs(include_status=True, function_id=uid)
        assert jobs_with_status.items
        for item in jobs_with_status.items:
            # Traverse nested discriminated unions to find the inner object
            obj = item
            while hasattr(obj, "actual_instance"):
                obj = obj.actual_instance
            assert hasattr(obj, "status")

        _delete_function_and_jobs(functions_api, function_jobs_api, uid)
        files_api.delete_file(input_file.id)


class TestMapFunction:
    """Map a function over multiple input sets."""

    def test_map_function(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        function_job_collections_api: osparc_client.FunctionJobCollectionsApi,  # noqa: ARG002
        sleeper_key_and_version: tuple[str, str],
        files_api: osparc_client.FilesApi,
        tmp_path_factory: pytest.TempPathFactory,
    ):
        solver_key, solver_version = sleeper_key_and_version

        tmpdir = tmp_path_factory.mktemp("map_input")
        input_path = tmpdir / "single_number.txt"
        input_path.write_text("3")
        input_file = files_api.upload_file(file=str(input_path))

        func = _build_solver_function(
            solver_key,
            solver_version,
            title="map-test",
            default_inputs={"input_1": input_file},
        )
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        # map over 2 input sets
        inputs_list = [
            {"input_2": 1, "input_3": False, "input_4": 0},
            {"input_2": 1, "input_3": False, "input_4": 1},
        ]

        collection = functions_api.map_function(
            function_id=uid,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            _headers=_NULL_PARENT_HEADERS,
            request_body=inputs_list,
        )
        assert collection.job_ids
        assert len(collection.job_ids) == 2

        # wait for all jobs
        for job_uid in collection.job_ids:
            status = _wait_for_job(function_jobs_api, job_uid)
            assert status == "SUCCESS"

        # cleanup
        _delete_function_and_jobs(functions_api, function_jobs_api, uid)
        files_api.delete_file(input_file.id)


class TestFunctionJobCollections:
    """CRUD and status for function job collections."""

    def test_list_function_job_collections(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        function_job_collections_api: osparc_client.FunctionJobCollectionsApi,
        sleeper_key_and_version: tuple[str, str],
        files_api: osparc_client.FilesApi,
        tmp_path_factory: pytest.TempPathFactory,
    ):
        solver_key, solver_version = sleeper_key_and_version

        tmpdir = tmp_path_factory.mktemp("collection_list_input")
        input_path = tmpdir / "single_number.txt"
        input_path.write_text("3")
        input_file = files_api.upload_file(file=str(input_path))

        func = _build_solver_function(
            solver_key,
            solver_version,
            title="collection-list-test",
            default_inputs={"input_1": input_file},
        )
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        # create a collection via map
        collection = functions_api.map_function(
            function_id=uid,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            _headers=_NULL_PARENT_HEADERS,
            request_body=[{"input_2": 1, "input_3": False, "input_4": 0}],
        )
        collection_id = collection.uid

        # list collections filtered by function
        collections_page = function_job_collections_api.list_function_job_collections(has_function_id=str(uid))
        collection_uids = [c.uid for c in collections_page.items]
        assert collection_id in collection_uids

        # wait for jobs to finish
        for job_uid in collection.job_ids:
            _wait_for_job(function_jobs_api, job_uid)

        _delete_function_and_jobs(functions_api, function_jobs_api, uid)
        files_api.delete_file(input_file.id)

    def test_get_function_job_collection(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        function_job_collections_api: osparc_client.FunctionJobCollectionsApi,
        sleeper_key_and_version: tuple[str, str],
        files_api: osparc_client.FilesApi,
        tmp_path_factory: pytest.TempPathFactory,
    ):
        solver_key, solver_version = sleeper_key_and_version

        tmpdir = tmp_path_factory.mktemp("collection_get_input")
        input_path = tmpdir / "single_number.txt"
        input_path.write_text("3")
        input_file = files_api.upload_file(file=str(input_path))

        func = _build_solver_function(
            solver_key,
            solver_version,
            title="collection-get-test",
            default_inputs={"input_1": input_file},
        )
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        collection = functions_api.map_function(
            function_id=uid,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            _headers=_NULL_PARENT_HEADERS,
            request_body=[{"input_2": 1, "input_3": False, "input_4": 0}],
        )
        collection_id = collection.uid

        fetched = function_job_collections_api.get_function_job_collection(collection_id)
        assert fetched.uid == collection_id
        assert fetched.job_ids == collection.job_ids

        for job_uid in collection.job_ids:
            _wait_for_job(function_jobs_api, job_uid)

        _delete_function_and_jobs(functions_api, function_jobs_api, uid)
        files_api.delete_file(input_file.id)

    def test_function_job_collection_status(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        function_job_collections_api: osparc_client.FunctionJobCollectionsApi,
        sleeper_key_and_version: tuple[str, str],
        files_api: osparc_client.FilesApi,
        tmp_path_factory: pytest.TempPathFactory,
    ):
        solver_key, solver_version = sleeper_key_and_version

        tmpdir = tmp_path_factory.mktemp("collection_status_input")
        input_path = tmpdir / "single_number.txt"
        input_path.write_text("3")
        input_file = files_api.upload_file(file=str(input_path))

        func = _build_solver_function(
            solver_key,
            solver_version,
            title="collection-status-test",
            default_inputs={"input_1": input_file},
        )
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        collection = functions_api.map_function(
            function_id=uid,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            _headers=_NULL_PARENT_HEADERS,
            request_body=[
                {"input_2": 1, "input_3": False, "input_4": 0},
                {"input_2": 1, "input_3": False, "input_4": 1},
            ],
        )
        collection_id = collection.uid

        # poll collection status
        status = function_job_collections_api.function_job_collection_status(collection_id)
        assert status.status is not None
        assert len(status.status) == 2

        for job_uid in collection.job_ids:
            _wait_for_job(function_jobs_api, job_uid)

        # after all done, status should be terminal
        final_status = function_job_collections_api.function_job_collection_status(collection_id)
        for s in final_status.status:
            assert s in ("SUCCESS", "FAILED")

        _delete_function_and_jobs(functions_api, function_jobs_api, uid)
        files_api.delete_file(input_file.id)

    def test_function_job_collection_list_jobs(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        function_job_collections_api: osparc_client.FunctionJobCollectionsApi,
        sleeper_key_and_version: tuple[str, str],
        files_api: osparc_client.FilesApi,
        tmp_path_factory: pytest.TempPathFactory,
    ):
        solver_key, solver_version = sleeper_key_and_version

        tmpdir = tmp_path_factory.mktemp("collection_list_jobs_input")
        input_path = tmpdir / "single_number.txt"
        input_path.write_text("3")
        input_file = files_api.upload_file(file=str(input_path))

        func = _build_solver_function(
            solver_key,
            solver_version,
            title="collection-list-jobs-test",
            default_inputs={"input_1": input_file},
        )
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        collection = functions_api.map_function(
            function_id=uid,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            _headers=_NULL_PARENT_HEADERS,
            request_body=[
                {"input_2": 1, "input_3": False, "input_4": 0},
            ],
        )
        collection_id = collection.uid

        # list jobs in collection
        jobs = function_job_collections_api.function_job_collection_list_function_jobs(collection_id)
        assert len(jobs) == 1
        job_uids = [_get_job_uid(j) for j in jobs]
        assert set(job_uids) == set(collection.job_ids)

        for job_uid in collection.job_ids:
            _wait_for_job(function_jobs_api, job_uid)

        _delete_function_and_jobs(functions_api, function_jobs_api, uid)
        files_api.delete_file(input_file.id)

    def test_function_job_collection_list_jobs_page(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        function_job_collections_api: osparc_client.FunctionJobCollectionsApi,
        sleeper_key_and_version: tuple[str, str],
        files_api: osparc_client.FilesApi,
        tmp_path_factory: pytest.TempPathFactory,
    ):
        solver_key, solver_version = sleeper_key_and_version

        tmpdir = tmp_path_factory.mktemp("collection_page_input")
        input_path = tmpdir / "single_number.txt"
        input_path.write_text("3")
        input_file = files_api.upload_file(file=str(input_path))

        func = _build_solver_function(
            solver_key,
            solver_version,
            title="collection-page-test",
            default_inputs={"input_1": input_file},
        )
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        collection = functions_api.map_function(
            function_id=uid,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            _headers=_NULL_PARENT_HEADERS,
            request_body=[
                {"input_2": 1, "input_3": False, "input_4": 0},
                {"input_2": 1, "input_3": False, "input_4": 1},
            ],
        )
        collection_id = collection.uid

        # paginated list
        page = function_job_collections_api.function_job_collection_list_function_jobs_page(
            collection_id, limit=1, offset=0
        )
        assert len(page.items) == 1
        assert page.total == 2

        for job_uid in collection.job_ids:
            _wait_for_job(function_jobs_api, job_uid)

        _delete_function_and_jobs(functions_api, function_jobs_api, uid)
        files_api.delete_file(input_file.id)

    def test_delete_function_job_collection(
        self,
        functions_api: osparc_client.FunctionsApi,
        function_jobs_api: osparc_client.FunctionJobsApi,
        function_job_collections_api: osparc_client.FunctionJobCollectionsApi,
        sleeper_key_and_version: tuple[str, str],
        files_api: osparc_client.FilesApi,
        tmp_path_factory: pytest.TempPathFactory,
    ):
        solver_key, solver_version = sleeper_key_and_version

        tmpdir = tmp_path_factory.mktemp("collection_delete_input")
        input_path = tmpdir / "single_number.txt"
        input_path.write_text("3")
        input_file = files_api.upload_file(file=str(input_path))

        func = _build_solver_function(
            solver_key,
            solver_version,
            title="collection-delete-test",
            default_inputs={"input_1": input_file},
        )
        registered = functions_api.register_function(func.model_dump())
        uid = _get_function_uid(registered)

        collection = functions_api.map_function(
            function_id=uid,
            x_simcore_parent_project_uuid=None,
            x_simcore_parent_node_id=None,
            _headers=_NULL_PARENT_HEADERS,
            request_body=[{"input_2": 1, "input_3": False, "input_4": 0}],
        )
        collection_id = collection.uid

        for job_uid in collection.job_ids:
            _wait_for_job(function_jobs_api, job_uid)

        function_job_collections_api.delete_function_job_collection(collection_id)

        with pytest.raises(osparc_client.ApiException) as exc_info:
            function_job_collections_api.get_function_job_collection(collection_id)
        assert exc_info.value.status == 404

        _delete_function_and_jobs(functions_api, function_jobs_api, uid)
        files_api.delete_file(input_file.id)
