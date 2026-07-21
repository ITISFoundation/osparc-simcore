# pylint: disable=logging-fstring-interpolation
# pylint:disable=invalid-name
# pylint:disable=line-too-long
# pylint:disable=missing-function-docstring
# pylint:disable=missing-module-docstring
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=too-many-branches
# pylint:disable=too-many-locals
# pylint:disable=too-many-positional-arguments
# pylint:disable=too-many-statements
# pylint:disable=unused-argument
# pylint:disable=unused-variable

import base64
import json
import logging
import re
from collections.abc import Callable, Iterator
from typing import Any, Final
from urllib.parse import urlparse, urlunparse

import pytest
from playwright.sync_api import APIRequestContext, Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pydantic import AnyUrl
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import MINUTE, SECOND, RobustWebSocket, ServiceType, wait_for_service_running
from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_fixed,
)

_WAITING_FOR_SERVICE_TO_START: Final[int] = 5 * MINUTE
_WAITING_FOR_SERVICE_TO_APPEAR: Final[int] = 2 * MINUTE
_DEFAULT_RESPONSE_TO_WAIT_FOR: Final[re.Pattern] = re.compile(r"/flask/list_function_job_collections_for_functionid")

# Delay after each input blur to let React process onBlur state update
_REACT_BLUR_SETTLE_MS: Final[int] = 500

_STUDY_FUNCTION_NAME: Final[str] = "playwright_test_study_for_rsm"
_FUNCTION_NAME: Final[str] = "playwright_test_function"
EXPECTED_MOGA_KEY: Final[str] = "moga"

# Heuristically 10 minutes is enough for these jobs to run
# However, when the dv2 / dask restarts during the run, things get delayed
# Add factor 2 to handle this case
_SAMPLING_TIMEOUT: Final[int] = 2 * 10 * MINUTE

_FAILED_STATES: Final[set[str]] = {"failed", "failed partially", "error", "aborted"}
_LHS_SEED: Final[int] = 42
_NUM_SAMPLING_POINTS: Final[int] = 40
_PROJECT_RENAME_PERSISTENCE_ATTEMPTS: Final[int] = 10
_PROJECT_RENAME_PERSISTENCE_WAIT_SECONDS: Final[float] = 0.5
_SELECT_FUNCTION_MAX_ATTEMPTS: Final[int] = 3
_SELECT_FUNCTION_RETRY_WAIT_SECONDS: Final[int] = 2
_SAMPLING_STATUS_POLL_SECONDS: Final[int] = 5
_TEARDOWN_RETRY_WAIT_SECONDS: Final[float] = 5.0
_TEARDOWN_MAX_ATTEMPTS: Final[int] = 8
_TEARDOWN_FULL_WAIT_SECONDS: Final[float] = 10.0
_TEARDOWN_FULL_ATTEMPTS: Final[int] = 3
_EXPECTED_LHS_INPUT_VALUES: Final[list[float]] = [
    1.1852604487,
    1.4180537145,
    1.5227525095,
    1.5854643369,
    1.8790490261,
    2.2554447459,
    2.403950683,
    2.404167764,
    2.5347171132,
    2.6364247049,
    2.6506405887,
    2.7970640394,
    2.9110519961,
    3.6210622618,
    3.6293018368,
    3.7381801866,
    3.7415239226,
    4.2972565896,
    4.3708610696,
    4.8875051678,
    4.9613724437,
    5.104629858,
    5.6281099457,
    5.7228078847,
    6.3317311198,
    6.3879263578,
    6.4100351057,
    6.4679036671,
    6.5066760525,
    7.1580972386,
    7.3726532002,
    7.5879454763,
    8.0665836525,
    8.275576133,
    8.4919837672,
    8.795585312,
    9.5399698353,
    9.5564287577,
    9.6906882977,
    9.7291886695,
]


class _TeardownDeleteError(Exception):
    """Raised when a resource DELETE request fails (non-ok, non-404 status)."""


class _SamplingFailedError(Exception):
    """Raised when a sampling job reaches a terminal failed state.

    Raise an exception that is not an assert to let tenacity stop polling
    """


@retry(
    wait=wait_fixed(_TEARDOWN_RETRY_WAIT_SECONDS),
    stop=stop_after_attempt(_TEARDOWN_MAX_ATTEMPTS),
    retry=retry_if_exception_type(_TeardownDeleteError),
    before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    reraise=True,
)
def _attempt_delete(
    api_request_context: APIRequestContext,
    url: str,
    label: str,
    *,
    headers: dict[str, str] | None = None,
) -> None:
    kwargs: dict[str, Any] = {}
    if headers:
        kwargs["headers"] = headers
    resp = api_request_context.delete(url, **kwargs)
    if resp.status == 404:
        return  # Already gone — treat as success
    if resp.status in {200, 204}:
        logging.info("Deleted %s", label)
        return
    msg = f"Delete {label} returned status {resp.status}: {resp.text()[:200]}"
    raise _TeardownDeleteError(msg)


def _delete_with_retry(
    api_request_context: APIRequestContext,
    url: str,
    label: str,
    *,
    headers: dict[str, str] | None = None,
) -> None:
    """DELETE url with retries (tenacity), treating 404 as success."""
    try:
        _attempt_delete(api_request_context, url, label, headers=headers)
    except _TeardownDeleteError:
        logging.exception("Gave up deleting %s after %d attempts", label, _TEARDOWN_MAX_ATTEMPTS)


def _get_api_server_url(product_url: AnyUrl) -> str:
    """Derive the API server URL from the product URL.

    In osparc deployments, the API server is accessible at api.<hostname>:<port>.
    """
    parsed = urlparse(str(product_url))
    api_host = f"api.{parsed.hostname}"
    api_netloc = f"{api_host}:{parsed.port}" if parsed.port else api_host
    return urlunparse(parsed._replace(netloc=api_netloc))


@retry(
    wait=wait_fixed(_TEARDOWN_FULL_WAIT_SECONDS),
    stop=stop_after_attempt(_TEARDOWN_FULL_ATTEMPTS),
    retry=retry_if_exception_type(AssertionError),
    before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    reraise=True,
)
def _teardown_function(  # noqa: C901
    api_request_context: APIRequestContext,
    api_server_url: str,
    product_url: AnyUrl,
    function_data: dict[str, Any],
    auth_headers: dict[str, str],
) -> None:
    """Delete all resources for a single function (collections, jobs, function, source study).

    Retried by tenacity until the function is confirmed deleted (404).
    """
    function_uuid = function_data["uuid"]
    template_id = function_data.get("templateId")
    limit = 50

    # 1. Delete all function_job_collections for this function
    for offset in range(0, 100_000, limit):
        collections_resp = api_request_context.get(
            f"{api_server_url}v0/function_job_collections?has_function_id={function_uuid}&limit={limit}&offset={offset}",
            headers=auth_headers,
        )
        if not collections_resp.ok:
            if collections_resp.status != 404:
                logging.warning(
                    "Could not list function_job_collections for %s: %s",
                    function_uuid,
                    collections_resp.text()[:200],
                )
            break
        collections = collections_resp.json().get("items", [])
        for collection in collections:
            _delete_with_retry(
                api_request_context,
                f"{api_server_url}v0/function_job_collections/{collection['uid']}",
                f"function_job_collection {collection['uid']}",
                headers=auth_headers,
            )
        if len(collections) < limit:
            break

    # 2. Delete all function_jobs and their associated comp projects
    for offset in range(0, 100_000, limit):
        jobs_resp = api_request_context.get(
            f"{api_server_url}v0/function_jobs?function_id={function_uuid}&limit={limit}&offset={offset}",
            headers=auth_headers,
        )
        if not jobs_resp.ok:
            if jobs_resp.status != 404:
                logging.warning(
                    "Could not list function_jobs for %s: %s",
                    function_uuid,
                    jobs_resp.text()[:200],
                )
            break
        jobs = jobs_resp.json().get("items", [])
        for job in jobs:
            job_uid = job["uid"]
            project_job_id = job.get("project_job_id")
            _delete_with_retry(
                api_request_context,
                f"{api_server_url}v0/function_jobs/{job_uid}",
                f"function_job {job_uid}",
                headers=auth_headers,
            )
            if project_job_id:
                _delete_with_retry(
                    api_request_context,
                    f"{product_url}v0/projects/{project_job_id}",
                    f"comp project {project_job_id}",
                )
        if len(jobs) < limit:
            break

    # 3. Delete the function itself (functions live on the api-server, not web-server)
    _delete_with_retry(
        api_request_context,
        f"{api_server_url}v0/functions/{function_uuid}",
        f"function {function_uuid}",
        headers=auth_headers,
    )

    # 4. Delete the source study the function was created from
    if template_id:
        _delete_with_retry(
            api_request_context,
            f"{product_url}v0/projects/{template_id}",
            f"source study {template_id}",
        )

    # Verify the function is gone — if not, AssertionError triggers a tenacity retry
    check_resp = api_request_context.get(
        f"{api_server_url}v0/functions/{function_uuid}",
        headers=auth_headers,
    )
    assert check_resp.status == 404, (
        f"Function {function_uuid} still exists after teardown (status {check_resp.status})"
    )


def _reload_page_before_retry(retry_state) -> None:
    page = retry_state.kwargs["page"]
    service_iframe = retry_state.kwargs["service_iframe"]
    logging.warning(
        "Attempt %d/%d failed to find/select function row, reloading page and retrying...",
        retry_state.attempt_number,
        _SELECT_FUNCTION_MAX_ATTEMPTS,
    )
    page.reload()
    service_iframe.locator("body").wait_for(state="visible", timeout=60 * SECOND)


def _refresh_sampling_before_retry(retry_state) -> None:
    page = retry_state.kwargs["page"]
    refresh_btn = retry_state.kwargs["refresh_btn"]
    logging.info("⏳ Waiting for all status cells to be completed...")
    try:
        refresh_btn.click(timeout=30 * SECOND)
    except PlaywrightTimeoutError:
        logging.warning("Refresh button click timed out, retrying after short wait...")
        page.wait_for_timeout(2 * SECOND)
        refresh_btn.click(timeout=60 * SECOND)


@retry(
    wait=wait_fixed(_SELECT_FUNCTION_RETRY_WAIT_SECONDS),
    stop=stop_after_attempt(_SELECT_FUNCTION_MAX_ATTEMPTS),
    retry=retry_if_exception_type(PlaywrightTimeoutError),
    before_sleep=_reload_page_before_retry,
    reraise=True,
)
def _select_test_function(*, page: Page, service_iframe, function_uuid: str, local_service_key: str) -> None:
    # Find the exact row by function UUID (data-id attribute in the MUI DataGrid)
    # The DataGrid paginates (10 per page), so navigate pages to find our function
    function_row = service_iframe.locator(f'div[role="row"][data-id="{function_uuid}"]')

    # Wait for the DataGrid to have at least one row rendered
    service_iframe.locator('div[role="row"][data-id]').first.wait_for(
        state="visible", timeout=_WAITING_FOR_SERVICE_TO_APPEAR
    )

    # Navigate through pages to find the function row
    for _ in range(20):  # max 20 pages
        if function_row.is_visible():
            break
        next_page_btn = service_iframe.locator('button[aria-label="Go to next page"]')
        if next_page_btn.count() == 0 or not next_page_btn.is_enabled():
            break
        next_page_btn.click()
        service_iframe.locator('div[role="row"][data-id]').first.wait_for(state="visible", timeout=60 * SECOND)
    function_row.wait_for(state="visible", timeout=30 * SECOND)

    select_btn = function_row.locator('[mmux-testid="select-function-btn"]')
    select_btn.wait_for(state="visible", timeout=30 * SECOND)

    # Wait for MUI DataGrid loading overlay to disappear before clicking
    overlay = service_iframe.locator(".MuiDataGrid-overlay")
    try:
        overlay.wait_for(state="hidden", timeout=60 * SECOND)
        select_btn.click(timeout=30 * SECOND)
    except PlaywrightTimeoutError:
        logging.warning("Overlay still present after 60s, clicking with force=True")
        select_btn.click(force=True, timeout=30 * SECOND)

    # Verify the click actually navigated to the input step
    min_test_id = "Mean" if "uq" in local_service_key.lower() else "Min"
    input_locator = service_iframe.locator(f'[mmux-testid="input-block-{min_test_id}"] input[type="number"]')
    input_locator.first.wait_for(state="visible", timeout=10 * SECOND)


@retry(
    wait=wait_fixed(_PROJECT_RENAME_PERSISTENCE_WAIT_SECONDS),
    stop=stop_after_attempt(_PROJECT_RENAME_PERSISTENCE_ATTEMPTS),
    retry=retry_if_exception_type(AssertionError),
    reraise=True,
)
def _assert_project_name_persisted(
    *,
    api_request_context: APIRequestContext,
    product_url: AnyUrl,
    project_uuid: str,
    expected_project_name: str,
) -> None:
    get_prj_resp = api_request_context.get(f"{product_url}v0/projects/{project_uuid}")
    assert get_prj_resp.ok, f"Failed to GET project: {get_prj_resp.status} {get_prj_resp.text()}"
    actual_project_name = get_prj_resp.json()["data"]["name"]
    assert actual_project_name == expected_project_name, (
        f"Project name was not persisted as '{expected_project_name}', server still reports '{actual_project_name}'"
    )


@retry(
    wait=wait_fixed(_SAMPLING_STATUS_POLL_SECONDS),
    stop=stop_after_delay(_SAMPLING_TIMEOUT / 1000),
    retry=retry_if_exception_type(AssertionError),
    before_sleep=_refresh_sampling_before_retry,
    reraise=True,
)
def _assert_sampling_completed(
    *,
    service_iframe,
    page: Page,
    refresh_btn,
    check_sampling_status: Callable[[Any, Page], str],
) -> None:
    status = check_sampling_status(service_iframe, page)
    if status == "failed":
        msg = "Sampling job failed! Check the deployment logs."
        raise _SamplingFailedError(msg)
    assert status == "complete", "Sampling is still running"


@pytest.fixture
def create_function_from_project(
    api_request_context: APIRequestContext,
    api_key_and_secret: tuple[str, str],
    is_product_billable: bool,
    product_url: AnyUrl,
) -> Iterator[Callable[[Page, str], dict[str, Any]]]:
    # Store full function data (including templateId for source study cleanup)
    created_functions: list[dict[str, Any]] = []

    def _create_function_from_project(
        page: Page,
        project_uuid: str,
    ) -> dict[str, Any]:
        with log_context(
            logging.INFO,
            f"Convert {project_uuid=} / {_STUDY_FUNCTION_NAME} to a function",
        ) as ctx:
            with page.expect_response(re.compile(rf"/projects/{project_uuid}")):
                page.get_by_test_id(f"studyBrowserListItem_{project_uuid}").click()
            page.get_by_text("create function").first.wait_for(state="visible", timeout=10 * SECOND)
            page.get_by_text("create function").first.click()
            page.get_by_test_id("create_function_page_btn").wait_for(state="visible", timeout=10 * SECOND)

            with page.expect_response(
                lambda response: (
                    re.compile(r"/functions").search(response.url) is not None and response.request.method == "POST"
                )
            ) as create_function_response:
                page.get_by_test_id("create_function_page_btn").click()
            assert create_function_response.value.ok, (
                f"Failed to create function: {create_function_response.value.status}"
            )
            function_data = create_function_response.value.json()

            ctx.logger.info("Created function: %s", f"{json.dumps(function_data['data'], indent=2)}")

            page.keyboard.press("Escape")
            created_functions.append(function_data["data"])
        return function_data["data"]

    yield _create_function_from_project

    # --- Teardown: runs even if the test fails ---
    api_server_url = _get_api_server_url(product_url)
    api_key, api_secret = api_key_and_secret
    credentials = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
    auth_headers = {"Authorization": f"Basic {credentials}"}

    for function_data in created_functions:
        try:
            _teardown_function(
                api_request_context,
                api_server_url,
                product_url,
                function_data,
                auth_headers,
            )
        except RetryError:
            logging.exception(
                "Function %s could not be fully cleaned up after %d attempts",
                function_data.get("uuid"),
                _TEARDOWN_FULL_ATTEMPTS,
            )


def test_response_surface_modeling(  # noqa: PLR0912, PLR0915, C901
    page: Page,
    create_project_from_service_dashboard: Callable[[ServiceType, str, str | None, str | None], dict[str, Any]],
    log_in_and_out: RobustWebSocket,
    service_version: str | None,
    product_url: AnyUrl,
    is_service_legacy: bool,
    create_function_from_project: Callable[[Page, str], dict[str, Any]],
    api_request_context: APIRequestContext,
    api_key_and_secret: tuple[str, str],
):
    # 1. create the initial study with two chained jsonifiers
    with log_context(logging.INFO, "Create new study for function"):
        jsonifier_project_data = create_project_from_service_dashboard(
            ServiceType.COMPUTATIONAL, "jsonifier", None, service_version
        )
        assert "workbench" in jsonifier_project_data, "Expected workbench to be in project data!"
        assert isinstance(jsonifier_project_data["workbench"], dict), "Expected workbench to be a dict!"
        node_ids: list[str] = list(jsonifier_project_data["workbench"])
        assert len(node_ids) == 1, "Expected 1 node in the workbench!"

        jsonifier_prj_uuid = jsonifier_project_data["uuid"]
        jsonifier_1_node_id = node_ids[0]

        # Select the first jsonifier (it's the second "jsonifier" in the tree
        # because the study itself has "jsonifier" in its name)
        page.get_by_test_id("nodeTreeItem").filter(has_text="jsonifier").all()[1].click()
        page.get_by_test_id("connect_input_btn_number_1").wait_for(state="visible", timeout=10 * SECOND)

        with log_context(logging.INFO, "Create parameter on jsonifier_1.number_1"):
            page.get_by_test_id("connect_input_btn_number_1").click()

            with (
                page.expect_response(
                    lambda resp: resp.url.endswith(f"/projects/{jsonifier_prj_uuid}") and resp.request.method == "PATCH"
                ) as patch_prj_param_ctx,
                page.expect_response(
                    lambda resp: (
                        resp.url.endswith(f"/projects/{jsonifier_prj_uuid}/nodes") and resp.request.method == "POST"
                    )
                ) as create_param_ctx,
            ):
                page.get_by_text("new parameter").click()

            patch_prj_param_resp = patch_prj_param_ctx.value
            assert patch_prj_param_resp.status == 204, f"Expected 204 from PATCH, got {patch_prj_param_resp.status}"
            create_param_resp = create_param_ctx.value
            assert create_param_resp.status == 201, f"Expected 201 from POST, got {create_param_resp.status}"
            page.wait_for_timeout(3 * SECOND)

        with log_context(logging.INFO, "Add second jsonifier node via API"):
            add_node_response = api_request_context.post(
                f"{product_url}v0/projects/{jsonifier_prj_uuid}/nodes",
                data=json.dumps(
                    {
                        "service_key": "simcore/services/comp/jsonifier",
                        "service_version": "1.2.1",
                    }
                ),
                headers={"Content-Type": "application/json"},
            )
            assert add_node_response.ok, (
                f"Failed to add second jsonifier: {add_node_response.status} {add_node_response.text()}"
            )
            jsonifier_2_node_id = add_node_response.json()["data"]["node_id"]
            logging.info("Added second jsonifier node: %s", jsonifier_2_node_id)
            page.wait_for_timeout(3 * SECOND)

        with log_context(logging.INFO, "Connect jsonifier_1.number_1 output -> jsonifier_2.number_1 input"):
            connect_response = api_request_context.patch(
                f"{product_url}v0/projects/{jsonifier_prj_uuid}/nodes/{jsonifier_2_node_id}",
                data=json.dumps(
                    {
                        "inputs": {
                            "number_1": {
                                "nodeUuid": jsonifier_1_node_id,
                                "output": "number_1",
                            }
                        },
                        "inputNodes": [jsonifier_1_node_id],
                    }
                ),
                headers={"Content-Type": "application/json"},
            )
            assert connect_response.status == 204, (
                f"Failed to connect nodes: {connect_response.status} {connect_response.text()}"
            )
            page.wait_for_timeout(3 * SECOND)

        with log_context(logging.INFO, "Add probe on jsonifier_2.number_1 via API"):
            add_probe_response = api_request_context.post(
                f"{product_url}v0/projects/{jsonifier_prj_uuid}/nodes",
                data=json.dumps(
                    {
                        "service_key": "simcore/services/frontend/iterator-consumer/probe/number",
                        "service_version": "1.0.0",
                    }
                ),
                headers={"Content-Type": "application/json"},
            )
            assert add_probe_response.ok, (
                f"Failed to add probe: {add_probe_response.status} {add_probe_response.text()}"
            )
            probe_node_id = add_probe_response.json()["data"]["node_id"]

            connect_probe_response = api_request_context.patch(
                f"{product_url}v0/projects/{jsonifier_prj_uuid}/nodes/{probe_node_id}",
                data=json.dumps(
                    {
                        "inputs": {
                            "in_1": {
                                "nodeUuid": jsonifier_2_node_id,
                                "output": "number_1",
                            }
                        },
                        "inputNodes": [jsonifier_2_node_id],
                    }
                ),
                headers={"Content-Type": "application/json"},
            )
            assert connect_probe_response.status == 204, (
                f"Failed to connect probe: {connect_probe_response.status} {connect_probe_response.text()}"
            )
            page.wait_for_timeout(3 * SECOND)

        # Wait for any pending auto-saves (from API node additions) to finish
        # before renaming, otherwise the auto-save may overwrite the new name
        with log_context(logging.INFO, "Wait for pending saves before rename"):
            page.get_by_test_id("savingStudyIcon").wait_for(state="hidden", timeout=5 * SECOND)

        with log_context(logging.INFO, "Rename project"):
            page.get_by_test_id("studyTitleRenamer").click()
            with page.expect_response(
                lambda resp: (
                    resp.url.endswith(f"/projects/{jsonifier_prj_uuid}")
                    and resp.request.method == "PATCH"
                    and '"name"' in (resp.request.post_data or "")
                    and _STUDY_FUNCTION_NAME in (resp.request.post_data or "")
                ),
                timeout=10 * SECOND,
            ) as patch_prj_rename_ctx:
                renamer = page.get_by_test_id("studyTitleRenamer").locator("input")
                renamer.fill(_STUDY_FUNCTION_NAME)
                renamer.press("Enter")

            patch_prj_rename_resp = patch_prj_rename_ctx.value
            assert patch_prj_rename_resp.status == 204, f"Expected 204 from PATCH, got {patch_prj_rename_resp.status}"

        # Wait until the rename save is finished
        with log_context(logging.INFO, "Wait until project is saved after rename"):
            page.get_by_test_id("savingStudyIcon").wait_for(state="hidden", timeout=30 * SECOND)

        with log_context(logging.INFO, "Verify project name was persisted on server"):
            _assert_project_name_persisted(
                api_request_context=api_request_context,
                product_url=product_url,
                project_uuid=jsonifier_prj_uuid,
                expected_project_name=_STUDY_FUNCTION_NAME,
            )

    # 2. go back to dashboard
    with (
        log_context(logging.INFO, "Go back to dashboard"),
        page.expect_response(re.compile(r"/projects\?.+")) as list_projects_response,
    ):
        page.get_by_test_id("dashboardBtn").click()
        page.get_by_test_id("confirmDashboardBtn").click()
    assert list_projects_response.value.ok, f"Failed to list projects: {list_projects_response.value.status}"
    project_listing = list_projects_response.value.json()
    assert "data" in project_listing
    assert len(project_listing["data"]) > 0
    # find our project by UUID (don't assume position in listing)
    our_project = next(
        (p for p in project_listing["data"] if p["uuid"] == jsonifier_prj_uuid),
        None,
    )
    assert our_project is not None, (
        f"Project {jsonifier_prj_uuid} not found in listing: {[p['uuid'] for p in project_listing['data']]}"
    )
    assert our_project["name"] == _STUDY_FUNCTION_NAME, (
        f"Expected project name '{_STUDY_FUNCTION_NAME}', got '{our_project['name']}'"
    )

    # 3. convert it to a function
    function_data = create_function_from_project(page, our_project["uuid"])
    function_uuid = function_data["uuid"]

    # 3. start a RSM with that function
    service_keys = [
        "mmux-vite-app-sumo-write",
        "mmux-vite-app-moga-write",
        "mmux-vite-app-uq-write",
    ]

    def _check_page_status(service_iframe) -> str:
        """Check status cells on the current page of the data grid."""
        status_cells = service_iframe.locator('div[role="gridcell"][data-field="status"]')
        total = status_cells.count()
        if total == 0:
            return "running"
        all_complete = True
        for i in range(total):
            text = (status_cells.nth(i).text_content() or "").lower().strip()
            logging.info("STATUS CELL TEXT %d: %s", i, text)
            if text in _FAILED_STATES:
                return "failed"
            if text != "complete":
                all_complete = False
        return "complete" if all_complete else "running"

    def check_all_pages_status(service_iframe, page) -> str:
        """Navigate through all data grid pages to check every row's status."""
        # Go to the first page
        first_page_btn = service_iframe.locator('button[aria-label="Go to first page"]')
        if first_page_btn.count() > 0 and first_page_btn.is_enabled():
            first_page_btn.click()
            page.wait_for_timeout(500)

        while True:
            status = _check_page_status(service_iframe)
            if status != "complete":
                return status

            # Try to go to the next page
            next_page_btn = service_iframe.locator('button[aria-label="Go to next page"]')
            if next_page_btn.count() == 0 or not next_page_btn.is_enabled():
                # No more pages — all rows across all pages are complete
                return "complete"

            next_page_btn.click()
            page.wait_for_timeout(500)

    for local_service_key in service_keys:
        with log_context(
            logging.INFO,
            f"Waiting for {local_service_key} to be responsive (waiting for {_DEFAULT_RESPONSE_TO_WAIT_FOR})",
        ):
            project_data = create_project_from_service_dashboard(
                ServiceType.DYNAMIC, local_service_key, None, service_version
            )
            assert "workbench" in project_data, "Expected workbench to be in project data!"
            assert isinstance(project_data["workbench"], dict), "Expected workbench to be a dict!"
            node_ids: list[str] = list(project_data["workbench"])
            assert len(node_ids) == 1, "Expected 1 node in the workbench!"

            service_iframe = wait_for_service_running(
                page=page,
                node_id=node_ids[0],
                websocket=log_in_and_out,
                timeout=_WAITING_FOR_SERVICE_TO_START,
                press_start_button=False,
                product_url=product_url,
                is_service_legacy=is_service_legacy,
            )

        with log_context(logging.INFO, "Waiting for the RSM iframe to be ready..."):
            service_iframe.locator("body").wait_for(state="visible", timeout=_WAITING_FOR_SERVICE_TO_APPEAR)

        with log_context(logging.INFO, "Selected test function..."):
            # Retry the whole selection in case of transient websocket/iframe issues.
            _select_test_function(
                page=page,
                service_iframe=service_iframe,
                function_uuid=function_uuid,
                local_service_key=local_service_key,
            )

        with log_context(logging.INFO, "Filling the input parameters..."):
            min_test_id = "Mean" if "uq" in local_service_key.lower() else "Min"
            min_inputs = service_iframe.locator(f'[mmux-testid="input-block-{min_test_id}"] input[type="number"]')
            min_inputs.first.wait_for(state="visible", timeout=30 * SECOND)
            count_min = min_inputs.count()
            logging.info("Found %d %s inputs", count_min, min_test_id)

            max_test_id = "Standard Deviation" if "uq" in local_service_key.lower() else "Max"
            max_inputs = service_iframe.locator(f'[mmux-testid="input-block-{max_test_id}"] input[type="number"]')
            max_inputs.first.wait_for(state="visible", timeout=30 * SECOND)
            count_max = max_inputs.count()
            logging.info("Found %d %s inputs", count_max, max_test_id)

            # Fill each pair of min/max together using native JS events to ensure
            # React's controlled input and onBlur handler are properly triggered
            for i in range(count_min):
                input_field = min_inputs.nth(i)
                value_str = str(i + 1)
                input_field.click()
                input_field.fill(value_str)
                # Use evaluate to explicitly trigger blur via native DOM API
                input_field.evaluate("el => el.blur()")
                if i < count_min - 1:
                    page.wait_for_timeout(_REACT_BLUR_SETTLE_MS)
                logging.info("Filled %s input %d with value %s", min_test_id, i, value_str)
                assert input_field.input_value() == value_str

            for i in range(count_max):
                input_field = max_inputs.nth(i)
                value_str = str((i + 1) * 10)
                input_field.click()
                input_field.fill(value_str)
                # Use evaluate to explicitly trigger blur via native DOM API
                input_field.evaluate("el => el.blur()")
                if i < count_max - 1:
                    page.wait_for_timeout(_REACT_BLUR_SETTLE_MS)
                logging.info("Filled %s input %d with value %s", max_test_id, i, value_str)
                assert input_field.input_value() == value_str

            page.wait_for_timeout(2 * SECOND)

            # Log the Next button state for debugging
            next_btn_disabled = service_iframe.locator('[mmux-testid="next-button"]').is_disabled()
            logging.info("Next button disabled after filling: %s", next_btn_disabled)

        if EXPECTED_MOGA_KEY in local_service_key.lower():
            with log_context(logging.INFO, "Filling the output parameters..."):
                output_plus_button = service_iframe.locator('[mmux-testid="add-output-var-btn"]')
                output_plus_button.wait_for(state="visible", timeout=_WAITING_FOR_SERVICE_TO_APPEAR)
                output_plus_button.scroll_into_view_if_needed()
                output_plus_button.click(timeout=30 * SECOND)

                output_confirm_button = service_iframe.locator('[mmux-testid="confirm-add-output-btn"]')
                output_confirm_button.wait_for(state="visible")
                output_confirm_button.click(timeout=30 * SECOND)

        # Click the next button
        with log_context(logging.INFO, "Clicking Next to go to the next step..."):
            next_button = service_iframe.locator('[mmux-testid="next-button"]')
            next_button.scroll_into_view_if_needed()
            try:
                next_button.click(timeout=60 * SECOND)
            except PlaywrightTimeoutError:
                if next_button.is_disabled():
                    logging.warning("Next button is disabled after 60s, re-filling inputs via JS events...")
                else:
                    logging.warning(
                        "Next button is enabled but click timed out"
                        " (possible overlay), re-filling inputs via JS events..."
                    )
                for i in range(count_min):
                    value_str = str(i + 1)
                    min_inputs.nth(i).evaluate(
                        """(el, val) => {
                            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                                window.HTMLInputElement.prototype, 'value').set;
                            nativeInputValueSetter.call(el, val);
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            el.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
                        }""",
                        value_str,
                    )
                    page.wait_for_timeout(_REACT_BLUR_SETTLE_MS)
                for i in range(count_max):
                    value_str = str((i + 1) * 10)
                    max_inputs.nth(i).evaluate(
                        """(el, val) => {
                            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                                window.HTMLInputElement.prototype, 'value').set;
                            nativeInputValueSetter.call(el, val);
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            el.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
                        }""",
                        value_str,
                    )
                    page.wait_for_timeout(_REACT_BLUR_SETTLE_MS)
                next_button.click(timeout=30 * SECOND)

        with log_context(logging.INFO, "Waiting for the AI model to be created..."):
            creating_ai_model_text = service_iframe.get_by_text("Creating AI model...")
            no_data_text = service_iframe.get_by_text("No data available. Please create more Samples.", exact=False)
            model_is_creating = False

            try:
                creating_ai_model_text.wait_for(state="visible", timeout=4 * SECOND)
                model_is_creating = True  # loading confirmation
            except PlaywrightTimeoutError:
                # if nothing was loaded, we check for no data and continue
                try:
                    expect(no_data_text).to_be_visible(timeout=10 * SECOND)
                    with log_context(logging.INFO, "No data available. Continuing test without data."):
                        pass
                except AssertionError:
                    # If there is no loading AND no 'no data' message, the test fails legitimately here
                    error_msg = "Neither the creation process nor the 'no data available' state was detected."
                    raise TimeoutError(error_msg) from None

            if model_is_creating:
                with log_context(logging.INFO, "Model creation in progress. Waiting up to 2 minutes for completion..."):
                    creating_ai_model_text.wait_for(state="hidden", timeout=2 * MINUTE)

        with log_context(logging.INFO, "Starting the sampling..."):
            extend_sampling_btn = service_iframe.locator('[mmux-testid="extend-sampling-btn"]')
            extend_sampling_btn.wait_for(state="visible", timeout=_WAITING_FOR_SERVICE_TO_APPEAR)
            extend_sampling_btn.scroll_into_view_if_needed()
            extend_sampling_btn.click(timeout=30 * SECOND)

            new_sampling_btn = service_iframe.locator('[mmux-testid="new-sampling-campaign-btn"]')
            new_sampling_btn.wait_for(state="visible", timeout=_WAITING_FOR_SERVICE_TO_APPEAR)
            new_sampling_btn.scroll_into_view_if_needed()
            new_sampling_btn.click(timeout=30 * SECOND)

            samplingInput = service_iframe.locator('input[placeholder="Number of sampling points"]')
            samplingInput.wait_for(state="attached", timeout=_WAITING_FOR_SERVICE_TO_APPEAR)
            samplingInput.scroll_into_view_if_needed()
            samplingInput.wait_for(state="visible", timeout=30 * SECOND)
            samplingInput.fill(str(_NUM_SAMPLING_POINTS))
            samplingInput.press("Enter")

            seed_was_set = False
            seed_input = service_iframe.locator('[mmux-testid="lhs-seed-input"] input')
            try:
                seed_input.wait_for(state="visible", timeout=5 * SECOND)
                seed_input.fill(str(_LHS_SEED))
                seed_input.press("Tab")
                seed_was_set = True
            except PlaywrightTimeoutError:
                logging.info("lhs-seed-input not available in this version, skipping seed setting")

            run_sampling_btn = service_iframe.locator('[mmux-testid="run-sampling-btn"]')
            run_sampling_btn.wait_for(state="attached", timeout=30 * SECOND)
            run_sampling_btn.scroll_into_view_if_needed()
            run_sampling_btn.click(timeout=30 * SECOND)

        with log_context(logging.INFO, "Waiting for the sampling to launch..."):
            toast = service_iframe.locator("div.Toastify__toast").filter(
                has_text="Sampling started running successfully, please wait for completion."
            )
            # waits up to 120 seconds
            toast.wait_for(state="visible", timeout=120000)

        with log_context(logging.INFO, "Waiting for the sampling to complete..."):
            refresh_btn = service_iframe.locator(
                '.MuiDataGrid-columnHeader[data-field="subJobs"] button:not(.MuiDataGrid-sortButton)'
            )
            try:
                refresh_btn.wait_for(state="visible", timeout=2 * MINUTE)
            except PlaywrightTimeoutError:
                logging.info("Refresh button not visible after 2min, trying to re-open accordion")
                extend_btn = service_iframe.locator('[mmux-testid="extend-sampling-btn"]')
                extend_btn.scroll_into_view_if_needed()
                extend_btn.click()
                page.wait_for_timeout(2 * SECOND)
                refresh_btn.wait_for(state="visible", timeout=30 * SECOND)

            _assert_sampling_completed(
                service_iframe=service_iframe,
                page=page,
                refresh_btn=refresh_btn,
                check_sampling_status=check_all_pages_status,
            )

        with log_context(logging.INFO, "Selecting jobs and verifying graph..."):
            select_all_btn = service_iframe.get_by_role("button", name="Select all successful Jobs")
            select_all_btn.wait_for(state="visible", timeout=30 * SECOND)
            select_all_btn.click()
            page.wait_for_timeout(2 * SECOND)

            if "uq" not in local_service_key.lower():
                plotly_graph = service_iframe.locator(".js-plotly-plot")
                plotly_graph.wait_for(state="visible", timeout=2 * MINUTE)
            page.wait_for_timeout(2000)

        if EXPECTED_MOGA_KEY in local_service_key.lower():
            with log_context(logging.INFO, "Verifying MOGA Pareto optimization produced some results..."):
                moga_pareto_container = service_iframe.locator('[mmux-testid="moga-pareto-plot"]')
                moga_pareto_container.wait_for(state="visible", timeout=2 * MINUTE)
                moga_pareto_plot = moga_pareto_container.locator(".js-plotly-plot")
                moga_pareto_plot.wait_for(state="visible", timeout=2 * MINUTE)

                moga_trace_lengths = moga_pareto_plot.evaluate(
                    "el => (el.data || []).map(trace => Math.max((trace.x || []).length, (trace.y || []).length))"
                )
                total_moga_points = sum(moga_trace_lengths)
                assert total_moga_points > 0, (
                    f"MOGA Pareto plot rendered but contains no data points (traces={moga_trace_lengths})"
                )
                logging.info("MOGA Pareto plot traces: %s", moga_trace_lengths)

        with log_context(logging.INFO, f"Verifying sampling results for {local_service_key}..."):
            api_server_url = _get_api_server_url(product_url)
            _api_key, _api_secret = api_key_and_secret
            credentials = base64.b64encode(f"{_api_key}:{_api_secret}".encode()).decode()
            auth_headers = {"Authorization": f"Basic {credentials}"}

            jobs_response = api_request_context.get(
                f"{api_server_url}v0/function_jobs?function_id={function_uuid}&limit=50",
                headers=auth_headers,
            )
            if jobs_response.status == 404:
                logging.warning(
                    "Endpoint /v0/function_jobs not available on %s — skipping API verification",
                    api_server_url,
                )
            else:
                assert jobs_response.ok, f"Failed to get function jobs: {jobs_response.status}"
                jobs_data = jobs_response.json()
                all_jobs = jobs_data.get("items", [])

                logging.info("Total jobs: %d", len(all_jobs))

                input_values = sorted(
                    [
                        j["inputs"]["Number Parameter"]
                        for j in all_jobs
                        if j.get("inputs") and "Number Parameter" in j["inputs"]
                    ]
                )

                logging.info(
                    "Input values for %s: %s",
                    local_service_key,
                    json.dumps(input_values),
                )

                if "uq" not in local_service_key.lower():
                    assert len(input_values) == _NUM_SAMPLING_POINTS, (
                        f"Expected {_NUM_SAMPLING_POINTS} input values, got {len(input_values)}"
                    )
                    if seed_was_set:
                        for i, (actual, expected) in enumerate(
                            zip(input_values, _EXPECTED_LHS_INPUT_VALUES, strict=True)
                        ):
                            assert abs(actual - expected) < 1e-4, f"Input value {i} mismatch: {actual} != {expected}"

        with (
            log_context(logging.INFO, "Go back to dashboard"),
            page.expect_response(re.compile(r"/projects\?.+")) as list_projects_response,
        ):
            page.get_by_test_id("dashboardBtn").click()
            page.get_by_test_id("confirmDashboardBtn").click()
        assert list_projects_response.value.ok, f"Failed to list projects: {list_projects_response.value.status}"
