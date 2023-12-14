import functools
import json
import re
from typing import Any

from attr import dataclass
from playwright.sync_api import Page, WebSocket

_NUM_SLEEPERS = 12


@dataclass(frozen=True, slots=True, kw_only=True)
class SocketIOEvent:
    name: str
    obj: dict[str, Any]


def _socketio_42_message(message: str) -> SocketIOEvent:
    data = json.loads(message.removeprefix("42"))
    return SocketIOEvent(name=data[0], obj=json.loads(data[1]))


def _wait_for_project_state_updated(message: str, *, expected_state: str) -> bool:
    print("<---- received websocket message:")
    print(message)
    if not message.startswith("42"):
        # socket.io encodes messages like so
        # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
        return False
    # now we have a message like ["messageEvent", data]
    decoded_message = _socketio_42_message(message)
    if decoded_message.name != "projectStateUpdated":
        return False
    assert decoded_message.obj["data"]["state"]["value"] == expected_state

    return True


def test_sleepers(page: Page, log_in_and_out: WebSocket, product_billable: bool):
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

    with log_in_and_out.expect_event(
        "framereceived",
        functools.partial(
            _wait_for_project_state_updated, expected_message="NOT_STARTED"
        ),
    ) as event, page.expect_response(re.compile(r"/projects/")):
        # Project detail view pop-ups shows
        page.get_by_test_id("openResource").click()
        if product_billable:
            # Open project with default resources
            page.get_by_test_id("openWithResources").click()

    # this allows to get the value back
    print(_socketio_42_message(event.value))

    # we are now in the workbench
    for i in range(1, _NUM_SLEEPERS):
        page.get_by_text("New Node").click()
        page.get_by_text("sleeperA service which").click()
        page.get_by_text("Add", exact=True).click()

    # start the sleepers
    # page.get_by_test_id("runStudyBtn").click()

    # check that we get waiting_for_cluster state for max 5 minutes

    # check that we get the starting/running state for max 5 minutes

    # check that we get success state now

    page.wait_for_timeout(10000)


# def test_example(page: Page) -> None:
#     page.goto("https://osparc-testing.click/")
#     page.get_by_placeholder(" Your email address").click()
#     page.get_by_placeholder(" Your email address").fill(
#         "playwright_testing_user@itis.testing"
#     )
#     page.get_by_placeholder(" Your password").click()
#     page.get_by_placeholder(" Your password").fill("whatanamazingpassword1234")
#     page.locator("div").filter(has_text=re.compile(r"^Sign in$")).nth(1).click()
#     page.get_by_text("SERVICES").click()
#     page.get_by_text("").click()
#     page.locator("div").filter(has_text=re.compile(r"^Open$")).first.click()
#     page.locator("#SvgjsSvg1001").click()
#     page.locator("div").filter(
#         has_text="MASTERpowered byDashboardsleeperPROJECTSTUTORIALSSERVICESDATACREDITS9999Im"
#     ).first.click(button="right")
#     page.locator("canvas").nth(2).click(position={"x": 81, "y": 43})
#     page.get_by_text(
#         "sleeperA service which awaits for time to pass, two times. v2.1.6Hits: 1"
#     ).click()
#     page.locator(".qx-pb-listitem > div:nth-child(3)").first.click()
#     page.get_by_text("").first.click()
#     page.get_by_text("").nth(2).click()
#     page.get_by_text("").click()
#     page.get_by_text("").click()
#     page.get_by_text("").click()
#     page.get_by_text("").click()
#     page.locator("div").filter(has_text=re.compile(r"^$")).first.click()
#     page.get_by_text("").click()
#     page.get_by_text("").click()
#     page.locator("div").filter(has_text=re.compile(r"^$")).first.click()
#     page.get_by_text("PROJECTS", exact=True).click()
