# pylint: disable=logging-fstring-interpolation
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=too-many-statements
# pylint:disable=unused-argument
# pylint:disable=unused-variable


import datetime
import logging
import re
from collections.abc import Callable
from typing import Any, Final

from packaging.version import Version
from packaging.version import parse as parse_version
from playwright.sync_api import Page
from pytest_simcore.helpers.logging_tools import (
    ContextMessages,
    log_context,
    test_logger,
)
from pytest_simcore.helpers.playwright import (
    MINUTE,
    RestartableWebSocket,
    RunningState,
    ServiceType,
    SocketIOEvent,
    retrieve_project_state_from_decoded_message,
    wait_for_pipeline_state,
)
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_fixed

_WAITING_FOR_PIPELINE_TO_CHANGE_STATE: Final[int] = 1 * MINUTE
_WAITING_FOR_CLUSTER_MAX_WAITING_TIME: Final[int] = 5 * MINUTE
_WAITING_FOR_STARTED_MAX_WAITING_TIME: Final[int] = 5 * MINUTE
_WAITING_FOR_SUCCESS_MAX_WAITING_TIME_PER_SLEEPER: Final[int] = 1 * MINUTE
_WAITING_FOR_FILE_NAMES_MAX_WAITING_TIME: Final[
    datetime.timedelta
] = datetime.timedelta(seconds=30)
_WAITING_FOR_FILE_NAMES_WAIT_INTERVAL: Final[datetime.timedelta] = datetime.timedelta(
    seconds=1
)

_VERSION_TO_EXPECTED_FILE_NAMES: Final[dict[Version, list[str]]] = {
    parse_version("1.0.0"): ["logs.zip", "single_number.txt"],
    parse_version("2.2.0"): ["dream.txt", "logs.zip", "single_number.txt"],
}


def _get_expected_file_names_for_version(version: Version) -> list[str]:
    for base_version, expected_file_names in reversed(
        _VERSION_TO_EXPECTED_FILE_NAMES.items()
    ):
        if version >= base_version:
            return expected_file_names
    return []


@retry(
    stop=stop_after_delay(_WAITING_FOR_FILE_NAMES_MAX_WAITING_TIME),
    retry=retry_if_exception_type(AssertionError),
    reraise=True,
    wait=wait_fixed(_WAITING_FOR_FILE_NAMES_WAIT_INTERVAL),
)
def _get_file_names(page: Page) -> list[str]:
    file_names_found = []
    for file in page.get_by_test_id("FolderViewerItem").all():
        file_name = file.text_content()
        assert file_name
        file_name = file_name.removesuffix("\ue24d")
        file_names_found.append(file_name)
    assert file_names_found

    return file_names_found


def test_sleepers(
    page: Page,
    log_in_and_out: RestartableWebSocket,
    create_project_from_service_dashboard: Callable[
        [ServiceType, str, str | None], dict[str, Any]
    ],
    start_and_stop_pipeline: Callable[..., SocketIOEvent],
    num_sleepers: int,
    input_sleep_time: int | None,
):
    project_data = create_project_from_service_dashboard(
        ServiceType.COMPUTATIONAL, "sleeper", "itis"
    )

    # we are now in the workbench
    with log_context(
        logging.INFO,
        f"create {num_sleepers} sleeper(s)...",
    ):
        for _ in range(1, num_sleepers):
            with page.expect_response(
                re.compile(rf"/projects/{project_data['uuid']}/nodes")
            ):
                page.get_by_test_id("newNodeBtn").click()
                page.get_by_placeholder("Filter").click()
                page.get_by_placeholder("Filter").fill("sleeper")
                page.get_by_placeholder("Filter").press("Enter")

    # get sleeper version
    sleeper_version = parse_version("1.0.0")
    sleeper_expected_output_files = _get_expected_file_names_for_version(
        sleeper_version
    )
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
            sleeper_expected_output_files = _get_expected_file_names_for_version(
                sleeper_version
            )
            ctx.logger.info(
                "we will expect the following outputs: %s",
                sleeper_expected_output_files,
            )
            page.keyboard.press("Escape")

            workbench_selector = page.get_by_test_id("desktopWindow")
            assert workbench_selector
            workbench_selector.click()
        break

    # set inputs if needed
    if input_sleep_time:
        for index, sleeper in enumerate(page.get_by_test_id("nodeTreeItem").all()[1:]):
            with log_context(
                logging.INFO, f"set sleeper {index} input time to {input_sleep_time}"
            ):
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
    # PUBLISHED -> [WAITING_FOR_CLUSTER] -> (PENDING) -> [WAITING_FOR_RESOURCES] -> (PENDING) -> STARTED -> SUCCESS/FAILED
    socket_io_event = start_and_stop_pipeline()
    current_state = retrieve_project_state_from_decoded_message(socket_io_event)
    test_logger.info("pipeline is in %s", f"{current_state=}")

    # this should not stay like this for long, it will either go to PENDING, WAITING_FOR_CLUSTER/WAITING_FOR_RESOURCES or STARTED or FAILED
    current_state = wait_for_pipeline_state(
        current_state,
        websocket=log_in_and_out,
        if_in_states=(
            RunningState.PUBLISHED,
            RunningState.PENDING,
        ),
        expected_states=(
            RunningState.WAITING_FOR_CLUSTER,
            RunningState.WAITING_FOR_RESOURCES,
            RunningState.STARTED,
        ),
        timeout_ms=_WAITING_FOR_PIPELINE_TO_CHANGE_STATE,
    )

    # in case we are in WAITING_FOR_CLUSTER, that means we have a new cluster OR that there is something restarting in a non billable deployment
    current_state = wait_for_pipeline_state(
        current_state,
        websocket=log_in_and_out,
        if_in_states=(RunningState.WAITING_FOR_CLUSTER,),
        expected_states=(
            RunningState.WAITING_FOR_RESOURCES,
            RunningState.STARTED,
        ),
        timeout_ms=_WAITING_FOR_CLUSTER_MAX_WAITING_TIME,
    )

    # now we wait for the workers
    current_state = wait_for_pipeline_state(
        current_state,
        websocket=log_in_and_out,
        if_in_states=(RunningState.WAITING_FOR_RESOURCES,),
        expected_states=(RunningState.STARTED,),
        timeout_ms=_WAITING_FOR_STARTED_MAX_WAITING_TIME,
    )

    # check that we get success state now
    current_state = wait_for_pipeline_state(
        current_state,
        websocket=log_in_and_out,
        if_in_states=(RunningState.STARTED,),
        expected_states=(RunningState.SUCCESS,),
        timeout_ms=num_sleepers * _WAITING_FOR_SUCCESS_MAX_WAITING_TIME_PER_SLEEPER,
    )

    # check the outputs (the first item is the title, so we skip it)
    with log_context(
        logging.INFO,
        ContextMessages(
            starting=f"-> Looking for {sleeper_expected_output_files=} in all {num_sleepers} sleeper services...",
            done="<- All good, we're done here! This was really great!",
            raised="! Error checking outputs!",
        ),
    ) as ctx:
        for index, sleeper in enumerate(page.get_by_test_id("nodeTreeItem").all()[1:]):
            sleeper.click()
            # waiting for this response is not enough, the frontend needs some time to show the files
            # therefore _get_file_names is wrapped with tenacity
            with page.expect_response(re.compile(r"files/metadata")):
                page.get_by_test_id("nodeFilesBtn").click()
                output_file_names_found = _get_file_names(page)

            msg = (
                f"found {output_file_names_found=} in sleeper {index} service outputs."
            )
            ctx.logger.info(msg)
            assert output_file_names_found == sleeper_expected_output_files
            page.get_by_test_id("nodeDataManagerCloseBtn").click()
