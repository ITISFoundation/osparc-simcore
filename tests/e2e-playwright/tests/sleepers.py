# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments


import json
import re
from collections.abc import Callable, Iterator
from typing import Any, Final

import pytest
from attr import dataclass
from playwright.sync_api import APIRequestContext, Page, WebSocket
from pydantic import AnyUrl


@dataclass(frozen=True, slots=True, kw_only=True)
class SocketIOEvent:
    name: str
    obj: dict[str, Any]


def _decode_socketio_42_message(message: str) -> SocketIOEvent:
    data = json.loads(message.removeprefix("42"))
    return SocketIOEvent(name=data[0], obj=json.loads(data[1]))


@dataclass
class SocketIOProjectStateUpdatedWaiter:
    expected_state: str

    def __call__(self, message: str) -> bool:
        # print(f"<---- received websocket {message=}")
        # socket.io encodes messages like so
        # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
        if message.startswith("42"):
            decoded_message = _decode_socketio_42_message(message)
            if decoded_message.name == "projectStateUpdated":
                return (
                    decoded_message.obj["data"]["state"]["value"] == self.expected_state
                )

        return False


_NUM_SLEEPERS = 12
_SECOND: Final[int] = 1000
_MINUTE: Final[int] = 60 * _SECOND
_WAITING_FOR_CLUSTER_MAX_WAITING_TIME: Final[int] = 5 * _MINUTE
_WAITING_FOR_STARTED_MAX_WAITING_TIME: Final[int] = 5 * _MINUTE
_WAITING_FOR_SUCCESS_MAX_WAITING_TIME: Final[int] = 3 * _MINUTE


@pytest.fixture
def start_and_stop_pipeline(
    product_url: AnyUrl,
    page: Page,
    log_in_and_out: WebSocket,
    api_request_context: APIRequestContext,
) -> Iterator[Callable[..., SocketIOEvent]]:
    started_pipeline_ids = []

    def _do() -> SocketIOEvent:
        waiter = SocketIOProjectStateUpdatedWaiter(expected_state="PUBLISHED")
        with page.expect_response(
            re.compile(r"/computations")
        ) as response_info, log_in_and_out.expect_event(
            "framereceived", waiter
        ) as event:
            page.get_by_test_id("runStudyBtn").click()
        assert response_info.value.ok, f"{response_info.value.json()}"
        response_body = response_info.value.json()
        assert "data" in response_body
        assert "pipeline_id" in response_body["data"]
        pipeline_id = response_body["data"]["pipeline_id"]
        started_pipeline_ids.append(pipeline_id)
        print(f"---> started {pipeline_id=}")
        return _decode_socketio_42_message(event.value)

    yield _do

    # ensure all the pipelines are stopped properly
    for pipeline_id in started_pipeline_ids:
        api_request_context.post(f"{product_url}v0/computations/{pipeline_id}:stop")


def test_sleepers(
    page: Page,
    log_in_and_out: WebSocket,
    product_billable: bool,
    start_and_stop_pipeline: Callable[..., SocketIOEvent],
):
    # open service tab and filter for sleeper
    page.get_by_test_id("servicesTabBtn").click()
    page.wait_for_timeout(3000)
    _textbox = page.get_by_test_id("searchBarFilter-textField-service")

    # _textbox = page.get_by_role("textbox", name="search")
    _textbox.fill("sleeper")
    _textbox.press("Enter")

    page.get_by_test_id(
        "studyBrowserListItem_simcore/services/comp/itis/sleeper"
    ).click()

    waiter = SocketIOProjectStateUpdatedWaiter(expected_state="NOT_STARTED")
    with log_in_and_out.expect_event("framereceived", waiter), page.expect_response(
        re.compile(r"/projects/")
    ):
        # Project detail view pop-ups shows
        page.get_by_test_id("openResource").click()
        if product_billable:
            # Open project with default resources
            page.get_by_test_id("openWithResources").click()

    # we are now in the workbench
    for _ in range(1, _NUM_SLEEPERS):
        page.get_by_text("New Node").click()
        page.get_by_text("sleeperA service which").click()
        page.get_by_text("Add", exact=True).click()

    # start the pipeline (depending on the state of the cluster, we might receive one of
    # in () are optional states depdending on the state of the clusters
    # PUBLISHED -> (WAITING_FOR_CLUSTER) -> PENDING -> (WAITING_FOR_RESOURCES) -> (PENDING) -> STARTED -> SUCCESS/FAILED
    socket_io_event = start_and_stop_pipeline()

    current_state = socket_io_event.obj["data"]["state"]["value"]
    print(f"---> pipeline is in {current_state=}")

    # check that we get waiting_for_cluster state for max 5 minutes
    if current_state == "WAITING_FOR_CLUSTER":
        waiter = SocketIOProjectStateUpdatedWaiter(
            expected_state="WAITING_FOR_RESOURCES"
        )
        print("---> waiting for WAITING_FOR_RESOURCE state...")
        with log_in_and_out.expect_event(
            "framereceived", waiter, timeout=_WAITING_FOR_CLUSTER_MAX_WAITING_TIME
        ) as event:
            ...
        current_state = _decode_socketio_42_message(event.value).obj["data"]["state"][
            "value"
        ]
        print(f"---> pipeline is in {current_state=}")

    # check that we get the starting/running state for max 5 minutes
    waiter = SocketIOProjectStateUpdatedWaiter(expected_state="STARTED")

    print("---> waiting for STARTED state...")
    with log_in_and_out.expect_event(
        "framereceived", waiter, timeout=_WAITING_FOR_STARTED_MAX_WAITING_TIME
    ) as event:
        ...
    current_state = _decode_socketio_42_message(event.value).obj["data"]["state"][
        "value"
    ]
    print(f"---> pipeline is in {current_state=}")

    # check that we get success state now
    waiter = SocketIOProjectStateUpdatedWaiter(expected_state="SUCCESS")
    print("---> waiting for SUCCESS state...")
    with log_in_and_out.expect_event(
        "framereceived", waiter, timeout=_WAITING_FOR_SUCCESS_MAX_WAITING_TIME
    ) as event:
        ...
    current_state = _decode_socketio_42_message(event.value).obj["data"]["state"][
        "value"
    ]
    print(f"---> pipeline is in {current_state=}")

    page.wait_for_timeout(1000)
