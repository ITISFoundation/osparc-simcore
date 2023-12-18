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
    SocketIOEvent,
    SocketIOProjectStateUpdatedWaiter,
    decode_socketio_42_message,
)
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_fixed

_NUM_SLEEPERS = 12
_WAITING_FOR_CLUSTER_MAX_WAITING_TIME: Final[int] = 5 * MINUTE
_WAITING_FOR_STARTED_MAX_WAITING_TIME: Final[int] = 5 * MINUTE
_WAITING_FOR_SUCCESS_MAX_WAITING_TIME: Final[int] = _NUM_SLEEPERS * 1 * MINUTE
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
    for _ in range(1, _NUM_SLEEPERS):
        page.get_by_text("New Node").click()
        page.get_by_text("sleeperA service which").click()
        page.get_by_text("Add", exact=True).click()

    # start the pipeline (depending on the state of the cluster, we might receive one of
    # in [] are optional states depending on the state of the clusters and if we have external clusters
    # sometimes they may jump
    # PUBLISHED -> [WAITING_FOR_CLUSTER] -> (PENDING) -> [WAITING_FOR_RESOURCES] -> (PENDING) -> STARTED -> SUCCESS/FAILED
    socket_io_event = start_and_stop_pipeline()

    current_state = socket_io_event.obj["data"]["state"]["value"]
    print(f"---> pipeline is in {current_state=}")

    # check that we get waiting_for_cluster state for max 5 minutes
    if product_billable and current_state in ["PUBLISHED", "WAITING_FOR_CLUSTER"]:
        waiter = SocketIOProjectStateUpdatedWaiter(
            expected_states=("WAITING_FOR_RESOURCES",)
        )
        print("---> waiting for WAITING_FOR_RESOURCE state...")
        with log_in_and_out.expect_event(
            "framereceived", waiter, timeout=_WAITING_FOR_CLUSTER_MAX_WAITING_TIME
        ) as event:
            ...
        current_state = decode_socketio_42_message(event.value).obj["data"]["state"][
            "value"
        ]
        print(f"---> pipeline is in {current_state=}")

    # check that we get the starting/running state for max 5 minutes
    if current_state != "STARTED":
        waiter = SocketIOProjectStateUpdatedWaiter(expected_states=("STARTED",))

        print("---> waiting for STARTED state...")
        with log_in_and_out.expect_event(
            "framereceived", waiter, timeout=_WAITING_FOR_STARTED_MAX_WAITING_TIME
        ) as event:
            ...
        current_state = decode_socketio_42_message(event.value).obj["data"]["state"][
            "value"
        ]
        print(f"---> pipeline is in {current_state=}")

    # check that we get success state now
    waiter = SocketIOProjectStateUpdatedWaiter(expected_states=("SUCCESS", "FAILED"))
    print("---> waiting for SUCCESS state...")
    with log_in_and_out.expect_event(
        "framereceived", waiter, timeout=_WAITING_FOR_SUCCESS_MAX_WAITING_TIME
    ) as event:
        ...
    current_state = decode_socketio_42_message(event.value).obj["data"]["state"][
        "value"
    ]
    print(f"---> pipeline is in {current_state=}")
    assert current_state == "SUCCESS", "pipeline failed to run!"

    # check the outputs (the first item is the title, so we skip it)
    expected_file_names = ["logs.zip", "single_number.txt"]
    print(
        f"---> looking for {expected_file_names=} in all {_NUM_SLEEPERS} sleeper services..."
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
