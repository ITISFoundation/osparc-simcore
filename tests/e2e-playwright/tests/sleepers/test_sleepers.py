# pylint: disable=logging-fstring-interpolation
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=too-many-statements
# pylint:disable=unused-argument
# pylint:disable=unused-variable


import logging
import re
from collections.abc import Callable
from typing import Any, Final

from packaging.version import Version
from packaging.version import parse as parse_version
from playwright.sync_api import APIRequestContext, Page
from pydantic import AnyUrl
from pytest_simcore.helpers.logging_tools import (
    ContextMessages,
    log_context,
    test_logger,
)
from pytest_simcore.helpers.playwright import (
    MINUTE,
    SECOND,
    PipelineStageTimeouts,
    RobustWebSocket,
    ServiceType,
    SocketIOEvent,
    check_node_outputs,
    retrieve_project_state_from_decoded_message,
    wait_for_computation_done,
    wait_for_nodes_outputs_updated,
)

_WAITING_FOR_SUCCESS_MAX_WAITING_TIME_PER_SLEEPER: Final[int] = 1 * MINUTE
# NOTE: small grace budget for stages a non-autoscaled deployment should never actually enter
_NON_AUTOSCALED_STAGE_GRACE_TIME: Final[int] = 30 * SECOND

_VERSION_TO_EXPECTED_FILE_NAMES: Final[dict[Version, list[str]]] = {
    parse_version("1.0.0"): ["logs.zip", "single_number.txt"],
    parse_version("2.2.0"): ["dream.txt", "logs.zip", "single_number.txt"],
}


def _get_expected_file_names_for_version(version: Version) -> list[str]:
    for base_version, expected_file_names in reversed(_VERSION_TO_EXPECTED_FILE_NAMES.items()):
        if version >= base_version:
            return expected_file_names
    return []


def test_sleepers(
    page: Page,
    api_request_context: APIRequestContext,
    product_url: AnyUrl,
    log_in_and_out: RobustWebSocket,
    create_project_from_service_dashboard: Callable[[ServiceType, str, str | None, str | None], dict[str, Any]],
    start_and_stop_pipeline: Callable[..., SocketIOEvent],
    num_sleepers: int,
    input_sleep_time: int | None,
    is_autoscaled: bool,
):
    project_data = create_project_from_service_dashboard(ServiceType.COMPUTATIONAL, "sleeper", "itis", None)

    # we are now in the workbench
    with log_context(
        logging.INFO,
        f"create {num_sleepers} sleeper(s)...",
    ):
        for _ in range(1, num_sleepers):
            with page.expect_response(re.compile(rf"/projects/{project_data['uuid']}/nodes")):
                page.get_by_test_id("newNodeBtn").click()
                page.get_by_placeholder("Filter").click()
                page.get_by_placeholder("Filter").fill("sleeper")
                page.get_by_placeholder("Filter").press("Enter")

    # get sleeper version
    sleeper_version = parse_version("1.0.0")
    sleeper_expected_output_files = _get_expected_file_names_for_version(sleeper_version)
    for index, sleeper in enumerate(page.get_by_test_id("nodeTreeItem").all()[1:]):
        with log_context(
            logging.INFO,
            f"get sleeper {index} version...",
        ) as ctx:
            sleeper.click()
            page.keyboard.press("i")
            version_string = page.get_by_test_id("serviceVersion").text_content()
            ctx.logger.info("found sleeper version: %s", version_string)
            assert version_string
            sleeper_version = parse_version(version_string)
            sleeper_expected_output_files = _get_expected_file_names_for_version(sleeper_version)
            ctx.logger.info(
                "we will expect the following outputs: %s",
                sleeper_expected_output_files,
            )
            page.keyboard.press("Escape")

            workbench_selector = page.get_by_test_id("desktopWindow")
            assert workbench_selector
            workbench_selector.click()
        break

    # collect all sleeper node ids upfront, so we can watch their websocket updates below
    sleeper_node_ids: list[str] = []
    for sleeper in page.get_by_test_id("nodeTreeItem").all()[1:]:
        node_id = sleeper.get_attribute("osparc-test-key")
        assert node_id
        sleeper_node_ids.append(node_id)

    # set inputs if needed
    if input_sleep_time:
        for index, sleeper in enumerate(page.get_by_test_id("nodeTreeItem").all()[1:]):
            with log_context(logging.INFO, f"set sleeper {index} input time to {input_sleep_time}"):
                sleeper.click()
                sleep_interval_selector = page.get_by_role("textbox").nth(1)
                sleep_interval_selector.click()
                sleep_interval_selector.fill(f"{input_sleep_time}")

        workbench_selector = page.get_by_test_id("desktopWindow")
        assert workbench_selector
        workbench_selector.click()
    # start the pipeline (depending on the state of the cluster, we might receive one of
    # in [] are optional states depending on the state of the clusters and if we have external clusters
    # sometimes they may jump
    # PUBLISHED -> [WAITING_FOR_CLUSTER] -> (PENDING) -> [WAITING_FOR_RESOURCES] ->
    # (PENDING) -> STARTED -> SUCCESS/FAILED
    # NOTE: asserts every sleeper actually pushes a NodeUpdated websocket message with its
    # outputs, instead of only relying on the after-the-fact REST check below
    # on non-autoscaled deployments the cluster/resources stages are never entered, so keep
    # their budget minimal instead of the full 5 min each (would otherwise slow down failures)
    stage_timeouts = PipelineStageTimeouts(
        waiting_for_cluster_ms=(5 * MINUTE) if is_autoscaled else _NON_AUTOSCALED_STAGE_GRACE_TIME,
        waiting_for_resources_ms=(5 * MINUTE) if is_autoscaled else _NON_AUTOSCALED_STAGE_GRACE_TIME,
        started_ms=num_sleepers * _WAITING_FOR_SUCCESS_MAX_WAITING_TIME_PER_SLEEPER,
    )
    with wait_for_nodes_outputs_updated(
        log_in_and_out,
        node_id_to_expected_number_of_outputs=dict.fromkeys(sleeper_node_ids, len(sleeper_expected_output_files)),
        # NOTE: covers every autoscaling stage (cold cluster/worker scale-up), not just STARTED
        timeout=stage_timeouts.total_ms,
    ):
        socket_io_event = start_and_stop_pipeline()
        current_state = retrieve_project_state_from_decoded_message(socket_io_event)
        test_logger.info("pipeline is in %s", f"{current_state=}")

        # handles the autoscaled-deployment state machine (cold cluster/worker scale-up can take
        # several minutes without the pipeline actually being stuck)
        current_state = wait_for_computation_done(
            current_state,
            websocket=log_in_and_out,
            stage_timeouts=stage_timeouts,
        )

    # NOTE: `project_data["workbench"]` predates the sleeper nodes created via the UI above, so
    # the project is re-fetched here to get an up-to-date workbench
    get_prj_response = api_request_context.get(f"{product_url}v0/projects/{project_data['uuid']}")
    assert get_prj_response.ok, f"Failed to GET project: {get_prj_response.status} {get_prj_response.text()}"
    workbench = get_prj_response.json()["data"]["workbench"]

    # check the outputs (the first item is the title, so we skip it)
    with log_context(
        logging.INFO,
        ContextMessages(
            starting=f"-> Looking for {sleeper_expected_output_files=} in all {num_sleepers} sleeper services...",
            done="<- All good, we're done here! This was really great!",
            raised="! Error checking outputs!",
        ),
    ):
        for sleeper in page.get_by_test_id("nodeTreeItem").all()[1:]:
            node_id = sleeper.get_attribute("osparc-test-key")
            assert node_id
            sleeper.click()
            check_node_outputs(
                page,
                study_id=project_data["uuid"],
                workbench=workbench,
                node_id=node_id,
                expected_file_names=sleeper_expected_output_files,
            )
