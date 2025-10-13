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
    SECOND,
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

        jsonifier_prj_uuid = jsonifier_project_data["uuid"]

        with log_context(logging.INFO, "Create probe"):
            with (
                page.expect_response(
                    lambda resp: resp.url.endswith(f"/projects/{jsonifier_prj_uuid}")
                    and resp.request.method == "PATCH"
                ) as patch_prj_probe_ctx,
                page.expect_response(
                    lambda resp: resp.url.endswith(
                        f"/projects/{jsonifier_prj_uuid}/nodes"
                    )
                    and resp.request.method == "POST"
                ) as create_probe_ctx,
            ):
                page.get_by_test_id("connect_probe_btn_number_3").click()

            patch_prj_probe_resp = patch_prj_probe_ctx.value
            assert (
                patch_prj_probe_resp.status == 204
            ), f"Expected 204 from PATCH, got {patch_prj_probe_resp.status}"
            create_probe_resp = create_probe_ctx.value
            assert (
                create_probe_resp.status == 201
            ), f"Expected 201 from POST, got {create_probe_resp.status}"

        with log_context(logging.INFO, "Create parameter"):
            page.get_by_test_id("connect_input_btn_number_1").click()

            with (
                page.expect_response(
                    lambda resp: resp.url.endswith(f"/projects/{jsonifier_prj_uuid}")
                    and resp.request.method == "PATCH"
                ) as patch_prj_param_ctx,
                page.expect_response(
                    lambda resp: resp.url.endswith(
                        f"/projects/{jsonifier_prj_uuid}/nodes"
                    )
                    and resp.request.method == "POST"
                ) as create_param_ctx,
            ):
                page.get_by_text("new parameter").click()

            patch_prj_param_resp = patch_prj_param_ctx.value
            assert (
                patch_prj_param_resp.status == 204
            ), f"Expected 204 from PATCH, got {patch_prj_param_resp.status}"
            create_param_resp = create_param_ctx.value
            assert (
                create_param_resp.status == 201
            ), f"Expected 201 from POST, got {create_param_resp.status}"

        with log_context(logging.INFO, "Rename project"):
            page.get_by_test_id("studyTitleRenamer").click()
            with page.expect_response(
                lambda resp: resp.url.endswith(f"/projects/{jsonifier_prj_uuid}")
                and resp.request.method == "PATCH"
            ) as patch_prj_rename_ctx:
                renamer = page.get_by_test_id("studyTitleRenamer").locator("input")
                renamer.fill(_STUDY_FUNCTION_NAME)
                renamer.press("Enter")

            patch_prj_rename_resp = patch_prj_rename_ctx.value
            assert (
                patch_prj_rename_resp.status == 204
            ), f"Expected 204 from PATCH, got {patch_prj_rename_resp.status}"

        # if the project is being saved, wait until it's finished
        with log_context(logging.INFO, "Wait until project is saved"):
            # Wait for the saving icon to disappear
            page.get_by_test_id("savingStudyIcon").wait_for(
                state="hidden", timeout=5 * SECOND
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

    with log_context(
        logging.INFO,
        f"Waiting for {service_key} to be responsive (waiting for {_DEFAULT_RESPONSE_TO_WAIT_FOR})",
    ):
        project_data = create_project_from_service_dashboard(
            ServiceType.DYNAMIC, service_key, None, service_version
        )
        assert "workbench" in project_data, "Expected workbench to be in project data!"
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

    page.wait_for_timeout(10000)

    # # select the function
    # service_iframe.get_by_role("gridcell", name=_FUNCTION_NAME).click()

    # # Find the first input field (textbox) in the iframe
    # min_input_field = service_iframe.get_by_role("textbox").nth(0)
    # min_input_field.fill("1")
    # max_input_field = service_iframe.get_by_role("textbox").nth(1)
    # max_input_field.fill("10")

    # # click on next
    # service_iframe.get_by_role("button", name="Next").click()

    # # then we wait a long time
    # page.wait_for_timeout(1 * MINUTE)
