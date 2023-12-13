from playwright.sync_api import Page


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
