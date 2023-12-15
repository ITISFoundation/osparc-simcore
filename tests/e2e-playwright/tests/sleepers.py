# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments
# pylint:disable=too-statements


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
    expected_states: tuple[str, ...]

    def __call__(self, message: str) -> bool:
        print(f"<---- received websocket {message=}")
        # socket.io encodes messages like so
        # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
        if message.startswith("42"):
            decoded_message = _decode_socketio_42_message(message)
            if decoded_message.name == "projectStateUpdated":
                return (
                    decoded_message.obj["data"]["state"]["value"]
                    in self.expected_states
                )

        return False


_NUM_SLEEPERS = 1
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
        print("----> starting computation...")
        waiter = SocketIOProjectStateUpdatedWaiter(
            expected_states=("PUBLISHED", "PENDING", "STARTED")
        )
        with page.expect_request(
            lambda request: re.search(r"/computations", request.url)
            and request.method.upper() == "POST"
        ) as request_info, log_in_and_out.expect_event(
            "framereceived", waiter
        ) as event:
            page.get_by_test_id("runStudyBtn").click()
        response = request_info.value.response()
        assert response
        assert response.ok, f"{response.json()}"
        response_body = response.json()
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


@pytest.fixture
def create_new_project_and_delete(
    page: Page,
    log_in_and_out: WebSocket,
    product_billable: bool,
    api_request_context: APIRequestContext,
    product_url: AnyUrl,
) -> Iterator[Callable[[bool], None]]:
    """The first available service currently displayed in the dashboard will be opened"""
    created_project_uuids = []

    def _do(auto_delete: bool) -> None:
        waiter = SocketIOProjectStateUpdatedWaiter(expected_states=("NOT_STARTED",))
        with log_in_and_out.expect_event("framereceived", waiter), page.expect_response(
            re.compile(r"/projects/[^:]+:open")
        ) as response_info:
            # Project detail view pop-ups shows
            page.get_by_test_id("openResource").click()
            if product_billable:
                # Open project with default resources
                page.get_by_test_id("openWithResources").click()
        project_data = response_info.value.json()
        assert project_data
        project_uuid = project_data["data"]["uuid"]
        print(f"---> opened {project_uuid}")
        if auto_delete:
            created_project_uuids.append(project_uuid)

    yield _do

    for project_uuid in created_project_uuids:
        api_request_context.delete(f"{product_url}v0/projects/{project_uuid}")


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
        current_state = _decode_socketio_42_message(event.value).obj["data"]["state"][
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
        current_state = _decode_socketio_42_message(event.value).obj["data"]["state"][
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
    current_state = _decode_socketio_42_message(event.value).obj["data"]["state"][
        "value"
    ]
    print(f"---> pipeline is in {current_state=}")
    assert current_state == "SUCCESS", "pipeline failed to run!"

    # check the outputs (the first item is the title, so we skip it)
    expected_file_names = ["logs.zip", "single_number.txt"]
    for sleeper in page.get_by_test_id("nodeTreeItem").all()[1:]:
        sleeper.click()
        page.get_by_test_id("outputsTabButton").click()
        with page.expect_response(re.compile(r"files/metadata")):
            page.get_by_test_id("nodeOutputFilesBtn").click()
            output_file_names_found = []
            # ensure the output window is up and filled.
            page.wait_for_timeout(1000)
            for file in page.get_by_test_id("FolderViewerItem").all():
                file_name = file.text_content()
                assert file_name
                file_name = file_name.removesuffix("\ue24d")
                print(f"found file named {file_name}")
                output_file_names_found.append(file_name)
        assert output_file_names_found == expected_file_names
        page.get_by_test_id("nodeDataManagerCloseBtn").click()
