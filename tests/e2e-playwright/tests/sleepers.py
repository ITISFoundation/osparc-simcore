import re

from playwright.sync_api import Page, WebSocket


def on_web_socket(ws: WebSocket) -> None:
    print(f"WebSocket opened: {ws.url}")
    ws.on("framesent", lambda payload: print(payload))
    ws.on("framereceived", lambda payload: print(payload))
    ws.on("close", lambda payload: print("WebSocket closed"))


def test_sleepers(page: Page, log_in_and_out: None, product_billable: bool):
    # connect and listen to websocket
    page.on("websocket", on_web_socket)

    # open service tab and filter for sleeper
    page.get_by_test_id("servicesTabBtn").click()
    _textbox = page.get_by_role("textbox", name="search")
    _textbox.fill("sleeper")
    _textbox.press("Enter")
    page.get_by_test_id(
        "studyBrowserListItem_simcore/services/comp/itis/sleeper"
    ).click()

    with page.expect_response(re.compile(r"/projects/")) as response_info:
        # Project detail view pop-ups shows
        page.get_by_test_id("openResource").click()
        if product_billable:
            # Open project with default resources
            page.get_by_test_id("openWithResources").click()
        page.wait_for_timeout(1000)


def test_example(page: Page) -> None:
    page.goto("https://osparc-testing.click/")
    page.get_by_placeholder(" Your email address").click()
    page.get_by_placeholder(" Your email address").fill(
        "playwright_testing_user@itis.testing"
    )
    page.get_by_placeholder(" Your password").click()
    page.get_by_placeholder(" Your password").fill("whatanamazingpassword1234")
    page.locator("div").filter(has_text=re.compile(r"^Sign in$")).nth(1).click()
    page.get_by_text("SERVICES").click()
    page.get_by_text("").click()
    page.locator("div").filter(has_text=re.compile(r"^Open$")).first.click()
    page.locator("#SvgjsSvg1001").click()
    page.locator("div").filter(
        has_text="MASTERpowered byDashboardsleeperPROJECTSTUTORIALSSERVICESDATACREDITS9999Im"
    ).first.click(button="right")
    page.locator("canvas").nth(2).click(position={"x": 81, "y": 43})
    page.get_by_text(
        "sleeperA service which awaits for time to pass, two times. v2.1.6Hits: 1"
    ).click()
    page.locator(".qx-pb-listitem > div:nth-child(3)").first.click()
    page.get_by_text("").first.click()
    page.get_by_text("").nth(2).click()
    page.get_by_text("").click()
    page.get_by_text("").click()
    page.get_by_text("").click()
    page.get_by_text("").click()
    page.locator("div").filter(has_text=re.compile(r"^$")).first.click()
    page.get_by_text("").click()
    page.get_by_text("").click()
    page.locator("div").filter(has_text=re.compile(r"^$")).first.click()
    page.get_by_text("PROJECTS", exact=True).click()
