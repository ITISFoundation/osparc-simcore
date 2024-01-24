# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments
# pylint:disable=too-many-statements


import datetime
import re
from collections.abc import Callable
from typing import Final

from playwright.sync_api import Page, WebSocket
from pytest_simcore.playwright_utils import (
    MINUTE,
    RunningState,
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
    log_in_and_out: WebSocket,
    create_new_project_and_delete: Callable[..., None],
    start_and_stop_pipeline: Callable[..., SocketIOEvent],
    product_billable: bool,
    num_sleepers: int,
    input_sleep_time: int | None,
):
    # open service tab and filter for sleeper
    page.get_by_test_id("servicesTabBtn").click()
    _textbox = page.get_by_test_id("searchBarFilter-textField-service")
    _textbox.fill("sleeper")
    _textbox.press("Enter")
    page.get_by_test_id(
        "studyBrowserListItem_simcore/services/comp/itis/sleeper"
    ).click()

    create_new_project_and_delete(auto_delete=True)

    # we are now in the workbench
    print(f"---> creating {num_sleepers} sleeper(s)...")
    for _ in range(1, num_sleepers):
        page.get_by_text("New Node").click()
        page.get_by_placeholder("Filter").click()
        page.get_by_placeholder("Filter").fill("sleeper")
        page.get_by_placeholder("Filter").press("Enter")
    print(f"<--- {num_sleepers} sleeper(s) created")

    # set inputs if needed
    if input_sleep_time:
        for index, sleeper in enumerate(page.get_by_test_id("nodeTreeItem").all()[1:]):
            print(f"---> setting sleeper {index} input time to {input_sleep_time}...")
            sleeper.click()
            sleep_interval_selector = page.get_by_role("textbox").nth(1)
            sleep_interval_selector.click()
            sleep_interval_selector.fill(f"{input_sleep_time}")
            print(f"<--- sleeper {index} input time set to {input_sleep_time}")

        workbench_selector = page.get_by_test_id("desktopWindow")
        assert workbench_selector
        workbench_selector.click()

    # start the pipeline (depending on the state of the cluster, we might receive one of
    # in [] are optional states depending on the state of the clusters and if we have external clusters
    # sometimes they may jump
    # PUBLISHED -> [WAITING_FOR_CLUSTER] -> (PENDING) -> [WAITING_FOR_RESOURCES] -> (PENDING) -> STARTED -> SUCCESS/FAILED
    socket_io_event = start_and_stop_pipeline()
    current_state = retrieve_project_state_from_decoded_message(socket_io_event)
    print(f"---> pipeline is in {current_state=}")

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
    expected_file_names = ["logs.zip", "single_number.txt"]
    print(
        f"---> looking for {expected_file_names=} in all {num_sleepers} sleeper services..."
    )

    for index, sleeper in enumerate(page.get_by_test_id("nodeTreeItem").all()[1:]):
        sleeper.click()
        page.get_by_test_id("outputsTabButton").click()
        # waiting for this response is not enough, the frontend needs some time to show the files
        # therefore _get_file_names is wrapped with tenacity
        with page.expect_response(re.compile(r"files/metadata")):
            page.get_by_test_id("nodeOutputFilesBtn").click()
            output_file_names_found = _get_file_names(page)
        print(
            f"<--- found {output_file_names_found=} in sleeper {index} service outputs."
        )
        assert output_file_names_found == expected_file_names
        page.get_by_test_id("nodeDataManagerCloseBtn").click()

    print("------------------------------------------------------")
    print("---> All good, we're done here! This was really great!")
    print("------------------------------------------------------")
