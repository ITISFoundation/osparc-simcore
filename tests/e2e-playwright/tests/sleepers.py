# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments


import re
from collections.abc import Callable
from typing import Final

from playwright.sync_api import Page, WebSocket
from pytest_simcore.playwright_utils import (
    SocketIOEvent,
    SocketIOProjectStateUpdatedWaiter,
    decode_socketio_42_message,
)

_NUM_SLEEPERS = 12
_SECOND: Final[int] = 1000
_MINUTE: Final[int] = 60 * _SECOND
_WAITING_FOR_CLUSTER_MAX_WAITING_TIME: Final[int] = 5 * _MINUTE
_WAITING_FOR_STARTED_MAX_WAITING_TIME: Final[int] = 5 * _MINUTE
_WAITING_FOR_SUCCESS_MAX_WAITING_TIME: Final[int] = 3 * _MINUTE


def test_sleepers(
    page: Page,
    log_in_and_out: WebSocket,
    create_new_project_and_delete: Callable[..., None],
    start_and_stop_pipeline: Callable[..., SocketIOEvent],
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
    # in () are optional states depdending on the state of the clusters
    # sometimes they may jump
    # PUBLISHED -> (WAITING_FOR_CLUSTER) -> PENDING -> (WAITING_FOR_RESOURCES) -> (PENDING) -> STARTED -> SUCCESS/FAILED
    socket_io_event = start_and_stop_pipeline()

    current_state = socket_io_event.obj["data"]["state"]["value"]
    print(f"---> pipeline is in {current_state=}")

    # check that we get waiting_for_cluster state for max 5 minutes
    if current_state == "WAITING_FOR_CLUSTER":
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
    for sleeper in page.get_by_test_id("nodeTreeItem").all()[1:]:
        sleeper.click()
        page.get_by_test_id("outputsTabButton").click()
        with page.expect_response(re.compile(r"files/metadata")):
            page.get_by_test_id("nodeOutputFilesBtn").click()
            output_file_names_found = []
            # ensure the output window is up and filled. this is very sad.
            page.wait_for_timeout(2000)
            for file in page.get_by_test_id("FolderViewerItem").all():
                file_name = file.text_content()
                assert file_name
                file_name = file_name.removesuffix("\ue24d")
                output_file_names_found.append(file_name)
        assert output_file_names_found == expected_file_names
        page.get_by_test_id("nodeDataManagerCloseBtn").click()
    print("------------------------------------------------------")
    print("---> All good, we're done here! This was really great!")
    print("------------------------------------------------------")
