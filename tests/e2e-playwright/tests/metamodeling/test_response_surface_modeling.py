# pylint: disable=logging-fstring-interpolation
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=too-many-statements
# pylint:disable=unused-argument
# pylint:disable=unused-variable

import base64
import json
import logging
import re
import time
from collections.abc import Callable, Iterator
from typing import Any, Final
from urllib.parse import urlparse, urlunparse

import pytest
from playwright.sync_api import APIRequestContext, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pydantic import AnyUrl
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import MINUTE, SECOND, RobustWebSocket, ServiceType, wait_for_service_running

_WAITING_FOR_SERVICE_TO_START: Final[int] = 5 * MINUTE
_WAITING_FOR_SERVICE_TO_APPEAR: Final[int] = 2 * MINUTE
_DEFAULT_RESPONSE_TO_WAIT_FOR: Final[re.Pattern] = re.compile(r"/flask/list_function_job_collections_for_functionid")

_STUDY_FUNCTION_NAME: Final[str] = "playwright_test_study_for_rsm"
_FUNCTION_NAME: Final[str] = "playwright_test_function"
EXPECTED_MOGA_KEY: Final[str] = "moga"
_SAMPLING_TIMEOUT: Final[int] = 10 * MINUTE
_FAILED_STATES: Final[set[str]] = {"failed", "failed partially", "error", "aborted"}
_LHS_SEED: Final[int] = 42
_NUM_SAMPLING_POINTS: Final[int] = 40
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


def _get_api_server_url(product_url: AnyUrl) -> str:
    """Derive the API server URL from the product URL.

    In osparc deployments, the API server is accessible at api.<hostname>:<port>.
    """
    parsed = urlparse(str(product_url))
    api_host = f"api.{parsed.hostname}"
    api_netloc = f"{api_host}:{parsed.port}" if parsed.port else api_host
    return urlunparse(parsed._replace(netloc=api_netloc))


@pytest.fixture
def create_function_from_project(
    api_request_context: APIRequestContext,
    is_product_billable: bool,
    product_url: AnyUrl,
) -> Iterator[Callable[[Page, str], dict[str, Any]]]:
    created_function_uuids: list[str] = []

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
            page.wait_for_timeout(2000)
            page.get_by_text("create function").first.click()
            page.wait_for_timeout(2000)

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
            created_function_uuids.append(function_data["data"]["uuid"])
        return function_data["data"]

    yield _create_function_from_project

    for function_uuid in created_function_uuids:
        with log_context(
            logging.INFO,
            f"Delete function with {function_uuid=} in {product_url=} as {is_product_billable=}",
        ):
            response = api_request_context.delete(f"{product_url}v0/functions/{function_uuid}")
            if response.status != 204:
                logging.warning("Could not delete function %s: %s", function_uuid, response.text())


def test_response_surface_modeling(  # noqa: PLR0915, C901
    page: Page,
    create_project_from_service_dashboard: Callable[[ServiceType, str, str | None, str | None], dict[str, Any]],
    log_in_and_out: RobustWebSocket,
    service_key: str,
    service_version: str | None,
    product_url: AnyUrl,
    is_service_legacy: bool,
    create_function_from_project: Callable[[Page, str], dict[str, Any]],
    api_request_context: APIRequestContext,
):
    # 1. create the initial study with two chained jsonifiers
    with log_context(logging.INFO, "Create new study for function"):
        jsonifier_project_data = create_project_from_service_dashboard(
            ServiceType.COMPUTATIONAL, "jsonifier", None, "1.2.1"
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

        with log_context(logging.INFO, "Rename project"):
            page.get_by_test_id("studyTitleRenamer").click()
            with page.expect_response(
                lambda resp: resp.url.endswith(f"/projects/{jsonifier_prj_uuid}") and resp.request.method == "PATCH"
            ) as patch_prj_rename_ctx:
                renamer = page.get_by_test_id("studyTitleRenamer").locator("input")
                renamer.fill(_STUDY_FUNCTION_NAME)
                renamer.press("Enter")

            patch_prj_rename_resp = patch_prj_rename_ctx.value
            assert patch_prj_rename_resp.status == 204, f"Expected 204 from PATCH, got {patch_prj_rename_resp.status}"

        # if the project is being saved, wait until it's finished
        with log_context(logging.INFO, "Wait until project is saved"):
            # Wait for the saving icon to disappear
            page.get_by_test_id("savingStudyIcon").wait_for(state="hidden", timeout=5 * SECOND)

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
    # find the project we just created, it's the first one
    our_project = project_listing["data"][0]
    assert our_project["name"] == _STUDY_FUNCTION_NAME, (
        f"Expected to find our project named {_STUDY_FUNCTION_NAME} in {project_listing}"
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
            select_btn = service_iframe.locator('[mmux-testid="select-function-btn"]').first
            select_btn.wait_for(state="visible", timeout=_WAITING_FOR_SERVICE_TO_APPEAR)
            select_btn.click()

        with log_context(logging.INFO, "Filling the input parameters..."):
            min_test_id = "Mean" if "uq" in local_service_key.lower() else "Min"
            min_inputs = service_iframe.locator(f'[mmux-testid="input-block-{min_test_id}"] input[type="number"]')
            count_min = min_inputs.count()

            for i in range(count_min):
                input_field = min_inputs.nth(i)
                input_field.fill(str(i + 1))
                logging.info("Filled %s input %d with value %d", min_test_id, i, i + 1)
                assert input_field.input_value() == str(i + 1)

            max_test_id = "Standard Deviation" if "uq" in local_service_key.lower() else "Max"
            max_inputs = service_iframe.locator(f'[mmux-testid="input-block-{max_test_id}"] input[type="number"]')
            count_max = max_inputs.count()

            for i in range(count_max):
                input_field = max_inputs.nth(i)
                input_field.fill(str((i + 1) * 10))
                logging.info("Filled %s input %d with value %d", max_test_id, i, (i + 1) * 10)
                assert input_field.input_value() == str((i + 1) * 10)

            page.wait_for_timeout(1000)
            page.keyboard.press("Tab")
            page.wait_for_timeout(1000)

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
            next_button.click(timeout=30 * SECOND)

        page.wait_for_timeout(1 * SECOND)

        with log_context(logging.INFO, "Waiting for the AI model to be created..."):
            creating_ai_model_text = service_iframe.get_by_text("Creating AI model...")
            # wait for it to disappear, which means the model is created and we can proceed
            creating_ai_model_text.wait_for(state="hidden", timeout=2 * MINUTE)

        with log_context(logging.INFO, "Starting the sampling..."):
            extend_sampling_btn = service_iframe.locator('[mmux-testid="extend-sampling-btn"]')
            extend_sampling_btn.wait_for(state="visible", timeout=_WAITING_FOR_SERVICE_TO_APPEAR)
            extend_sampling_btn.scroll_into_view_if_needed()
            extend_sampling_btn.click(timeout=30 * SECOND)
            page.wait_for_timeout(2 * SECOND)

            new_sampling_btn = service_iframe.locator('[mmux-testid="new-sampling-campaign-btn"]')
            new_sampling_btn.wait_for(state="visible", timeout=_WAITING_FOR_SERVICE_TO_APPEAR)
            new_sampling_btn.scroll_into_view_if_needed()
            new_sampling_btn.click(timeout=30 * SECOND)
            page.wait_for_timeout(2 * SECOND)

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

            def check_sampling_status(service_iframe) -> str:
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

            start_time = time.monotonic()
            while True:
                status = check_sampling_status(service_iframe)
                if status == "complete":
                    break
                assert status != "failed", "Sampling job failed! Check the deployment logs."
                elapsed = time.monotonic() - start_time
                assert elapsed < _SAMPLING_TIMEOUT / 1000, (
                    f"Sampling did not complete within {_SAMPLING_TIMEOUT / 1000}s"
                )
                logging.info("⏳ Waiting for all status cells to be completed...")
                page.wait_for_timeout(5000)
                refresh_btn.click()

            select_all_btn = service_iframe.get_by_role("button", name="Select all successful Jobs")
            select_all_btn.wait_for(state="visible", timeout=30 * SECOND)
            select_all_btn.click()

            if "uq" not in local_service_key.lower():
                plotly_graph = service_iframe.locator(".js-plotly-plot")
                plotly_graph.wait_for(state="visible", timeout=60 * SECOND)
            page.wait_for_timeout(2000)

        with log_context(logging.INFO, f"Verifying sampling results for {local_service_key}..."):
            api_server_url = _get_api_server_url(product_url)
            api_key_response = api_request_context.post(
                f"{product_url}v0/auth/api-keys",
                data=json.dumps({"displayName": f"e2e-test-{local_service_key}"}),
                headers={"Content-Type": "application/json"},
            )
            assert api_key_response.ok, f"Failed to create API key: {api_key_response.status}"
            api_key_data = api_key_response.json()["data"]
            credentials = base64.b64encode(f"{api_key_data['apiKey']}:{api_key_data['apiSecret']}".encode()).decode()
            auth_headers = {"Authorization": f"Basic {credentials}"}

            jobs_response = api_request_context.get(
                f"{api_server_url}v0/function_jobs?function_id={function_uuid}&limit=50",
                headers=auth_headers,
            )
            assert jobs_response.ok, f"Failed to get function jobs: {jobs_response.status}"
            jobs_data = jobs_response.json()
            all_jobs = jobs_data.get("items", [])

            logging.info("Total jobs: %d", len(all_jobs))

            input_values = sorted(
                [
                    j["inputs"]["Number parameter"]
                    for j in all_jobs
                    if j.get("inputs") and "Number parameter" in j["inputs"]
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
                    for i, (actual, expected) in enumerate(zip(input_values, _EXPECTED_LHS_INPUT_VALUES, strict=True)):
                        assert abs(actual - expected) < 1e-4, f"Input value {i} mismatch: {actual} != {expected}"

        with (
            log_context(logging.INFO, "Go back to dashboard"),
            page.expect_response(re.compile(r"/projects\?.+")) as list_projects_response,
        ):
            page.get_by_test_id("dashboardBtn").click()
            page.get_by_test_id("confirmDashboardBtn").click()
            assert list_projects_response.value.ok, f"Failed to list projects: {list_projects_response.value.status}"
            page.wait_for_timeout(2000)
