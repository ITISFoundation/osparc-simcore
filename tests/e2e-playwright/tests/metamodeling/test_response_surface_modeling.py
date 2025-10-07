# pylint: disable=logging-fstring-interpolation
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=too-many-statements
# pylint:disable=unused-argument
# pylint:disable=unused-variable

import json
import logging
import re
from collections.abc import Callable, Iterator
from typing import Any, Final

import pytest
from playwright.sync_api import APIRequestContext, Page
from pydantic import AnyUrl
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    RobustWebSocket,
    ServiceType,
    wait_for_service_running,
)

_WAITING_FOR_SERVICE_TO_START: Final[int] = 5 * MINUTE
_WAITING_FOR_SERVICE_TO_APPEAR: Final[int] = 2 * MINUTE
_DEFAULT_RESPONSE_TO_WAIT_FOR: Final[re.Pattern] = re.compile(
    r"/flask/list_function_job_collections_for_functionid"
)

_STUDY_FUNCTION_NAME: Final[str] = "playwright_test_study_for_rsm"
_FUNCTION_NAME: Final[str] = "playwright_test_function"


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
                lambda response: re.compile(r"/functions").search(response.url)
                is not None
                and response.request.method == "POST"
            ) as create_function_response:
                page.get_by_test_id("create_function_page_btn").click()
            assert (
                create_function_response.value.ok
            ), f"Failed to create function: {create_function_response.value.status}"
            function_data = create_function_response.value.json()

            ctx.logger.info(
                "Created function: %s", f"{json.dumps(function_data['data'], indent=2)}"
            )

            page.keyboard.press("Escape")
            created_function_uuids.append(function_data["data"]["uuid"])
        return function_data["data"]

    yield _create_function_from_project

    # cleanup the functions
    for function_uuid in created_function_uuids:
        with log_context(
            logging.INFO,
            f"Delete function with {function_uuid=} in {product_url=} as {is_product_billable=}",
        ):
            response = api_request_context.delete(
                f"{product_url}v0/functions/{function_uuid}"
            )
            assert (
                response.status == 204
            ), f"Unexpected error while deleting project: '{response.json()}'"


def test_response_surface_modeling(
    page: Page,
    create_project_from_service_dashboard: Callable[
        [ServiceType, str, str | None, str | None], dict[str, Any]
    ],
    log_in_and_out: RobustWebSocket,
    service_key: str,
    service_version: str | None,
    product_url: AnyUrl,
    is_service_legacy: bool,
    create_function_from_project: Callable[[Page, str], dict[str, Any]],
):
    # 1. create the initial study with jsonifier
    with log_context(logging.INFO, "Create new study for function"):
        jsonifier_project_data = create_project_from_service_dashboard(
            ServiceType.COMPUTATIONAL, "jsonifier", None, service_version
        )
        assert (
            "workbench" in jsonifier_project_data
        ), "Expected workbench to be in project data!"
        assert isinstance(
            jsonifier_project_data["workbench"], dict
        ), "Expected workbench to be a dict!"
        node_ids: list[str] = list(jsonifier_project_data["workbench"])
        assert len(node_ids) == 1, "Expected 1 node in the workbench!"

        # select the jsonifier, it's the second one as the study has the same name
        page.get_by_test_id("nodeTreeItem").filter(has_text="jsonifier").all()[
            1
        ].click()

        # create the probe
        with page.expect_response(
            lambda response: re.compile(
                rf"/projects/{jsonifier_project_data['uuid']}"
            ).search(response.url)
            is not None
            and response.request.method == "PATCH"
        ):
            page.get_by_test_id("connect_probe_btn_number_3").click()

        # # create the parameter
        page.get_by_test_id("connect_input_btn_number_1").click()
        with page.expect_response(
            lambda response: re.compile(
                rf"/projects/{jsonifier_project_data['uuid']}"
            ).search(response.url)
            is not None
            and response.request.method == "PATCH"
        ):
            page.get_by_text("new parameter").click()

        # rename the project to identify it
        page.get_by_test_id("studyTitleRenamer").click()
        with page.expect_response(
            lambda response: re.compile(
                rf"/projects/{jsonifier_project_data['uuid']}"
            ).search(response.url)
            is not None
            and response.request.method == "PATCH"
        ):
            page.get_by_test_id("studyTitleRenamer").locator("input").fill(
                _STUDY_FUNCTION_NAME
            )

    # 2. go back to dashboard
    with (
        log_context(logging.INFO, "Go back to dashboard"),
        page.expect_response(re.compile(r"/projects\?.+")) as list_projects_response,
    ):
        page.get_by_test_id("dashboardBtn").click()
        page.get_by_test_id("confirmDashboardBtn").click()
    assert (
        list_projects_response.value.ok
    ), f"Failed to list projects: {list_projects_response.value.status}"
    project_listing = list_projects_response.value.json()
    assert "data" in project_listing
    assert len(project_listing["data"]) > 0
    # find the project we just created, it's the first one
    our_project = project_listing["data"][0]
    assert (
        our_project["name"] == _STUDY_FUNCTION_NAME
    ), f"Expected to find our project named {_STUDY_FUNCTION_NAME} in {project_listing}"

    # 3. convert it to a function
    create_function_from_project(page, our_project["uuid"])

    # 3. start a RSM with that function
    service_keys = [
        "mmux-vite-app-moga-write",
        "mmux-vite-app-sumo-write",
        "mmux-vite-app-uq-write",
    ]

    for service_key in service_keys:
        with log_context(
            logging.INFO,
            f"Waiting for {service_key} to be responsive (waiting for {_DEFAULT_RESPONSE_TO_WAIT_FOR})",
        ):
            project_data = create_project_from_service_dashboard(
                ServiceType.DYNAMIC, service_key, None, service_version
            )
            assert (
                "workbench" in project_data
            ), "Expected workbench to be in project data!"
            assert isinstance(
                project_data["workbench"], dict
            ), "Expected workbench to be a dict!"
            node_ids: list[str] = list(project_data["workbench"])
            assert len(node_ids) == 1, "Expected 1 node in the workbench!"

            wait_for_service_running(
                page=page,
                node_id=node_ids[0],
                websocket=log_in_and_out,
                timeout=_WAITING_FOR_SERVICE_TO_START,
                press_start_button=False,
                product_url=product_url,
                is_service_legacy=is_service_legacy,
            )

        service_iframe = page.frame_locator("iframe")
        with log_context(logging.INFO, "Waiting for the RSM to be ready..."):
            service_iframe.get_by_role("grid").wait_for(
                state="visible", timeout=_WAITING_FOR_SERVICE_TO_APPEAR
            )

        # select the function
        with log_context(logging.INFO, "Selected test function..."):
            service_iframe.get_by_role("button", name="SELECT").nth(0).click()

        with log_context(logging.INFO, "Filling the input parameters..."):
            min_test_id = "Mean" if "uq" in service_key.lower() else "Min"
            min_inputs = service_iframe.locator(
                f'[mmux-testid="input-block-{min_test_id}"] input[type="number"]'
            )
            count_min = min_inputs.count()

            for i in range(count_min):
                input_field = min_inputs.nth(i)
                input_field.fill(str(i + 1))
                print(f"Filled {min_test_id} input {i} with value {i + 1}")
                assert input_field.input_value() == str(i + 1)

            max_test_id = "Standard Deviation" if "uq" in service_key.lower() else "Max"
            max_inputs = service_iframe.locator(
                f'[mmux-testid="input-block-{max_test_id}"] input[type="number"]'
            )
            count_max = max_inputs.count()

            for i in range(count_max):
                input_field = max_inputs.nth(i)
                input_field.fill(str((i + 1) * 10))
                print(f"Filled {max_test_id} input {i} with value {(i + 1) * 10}")
                assert input_field.input_value() == str((i + 1) * 10)

            page.wait_for_timeout(1000)
            page.keyboard.press("Tab")
            page.wait_for_timeout(1000)

        if "moga" in service_key.lower():
            with log_context(logging.INFO, "Filling the output parameters..."):
                output_plus_button = service_iframe.locator(
                    '[mmux-testid="add-output-var-btn"]'
                )

                output_plus_button.click()
                page.wait_for_timeout(1000)

                output_confirm_button = service_iframe.locator(
                    '[mmux-testid="confirm-add-output-btn"]'
                )
                output_confirm_button.click()
                page.wait_for_timeout(1000)

        # Click the next button
        with log_context(logging.INFO, "Clicking Next to go to the next step..."):
            service_iframe.locator('[mmux-testid="next-button"]').click()
            page.wait_for_timeout(1000)

        with log_context(logging.INFO, "Starting the sampling..."):
            service_iframe.locator('[mmux-testid="extend-sampling-btn"]').click()
            page.wait_for_timeout(1000)
            service_iframe.locator('[mmux-testid="new-sampling-campaign-btn"]').click()
            page.wait_for_timeout(1000)
            service_iframe.locator('[mmux-testid="run-sampling-btn"]').click()
            page.wait_for_timeout(1000)

        with log_context(logging.INFO, "Waiting for the sampling to complete..."):
            toast = service_iframe.locator("div.Toastify__toast").filter(
                has_text="Sampling started running successfully, please wait for completion."
            )
            toast.wait_for(state="visible", timeout=120000)  # waits up to 120 seconds

        with log_context(logging.INFO, "Waiting for the sampling to complete..."):
            plotly_graph = service_iframe.locator(".js-plotly-plot")
            plotly_graph.wait_for(state="visible", timeout=300000)
            page.wait_for_timeout(2000)

        with (
            log_context(logging.INFO, "Go back to dashboard"),
            page.expect_response(
                re.compile(r"/projects\?.+")
            ) as list_projects_response,
        ):
            page.get_by_test_id("dashboardBtn").click()
            page.get_by_test_id("confirmDashboardBtn").click()
            assert (
                list_projects_response.value.ok
            ), f"Failed to list projects: {list_projects_response.value.status}"
            page.wait_for_timeout(2000)

    # # then we wait a long time
    page.wait_for_timeout(1 * MINUTE)

    # TODO: more steps
    # Run this tests against MOGA, UQ and SUMO services before destroying the functions / jobs / etc..
    # 4. cleanup
    # - drop the Jobs created for the Function
    # - drop the function proper to avoid polluting the DB
    # - drop the jsonifier project
