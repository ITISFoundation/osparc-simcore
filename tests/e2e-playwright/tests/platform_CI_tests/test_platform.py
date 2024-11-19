# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=no-name-in-module

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def store_browser_context() -> bool:
    return True


@pytest.fixture
def logged_in_context(
    playwright, store_browser_context: bool, request: pytest.FixtureRequest
):
    file_path = Path("state.json")
    if not file_path.exists():
        request.getfixturevalue("log_in_and_out")

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(storage_state="state.json")
    yield context
    context.close()
    browser.close()


@pytest.fixture(scope="module")
def test_module_teardown():

    yield  # Run the tests

    file_path = Path("state.json")
    if file_path.exists():
        file_path.unlink()


def test_simple_folder_workflow(logged_in_context, product_url, test_module_teardown):
    page = logged_in_context.new_page()

    page.goto(f"{product_url}")
    page.wait_for_timeout(1000)
    page.get_by_test_id("dashboard").get_by_text("New folder", exact=True).click()
    page.get_by_placeholder("Title").fill("My new folder")
    page.get_by_placeholder("Title").press("Enter")

    page.get_by_test_id("dashboard").get_by_text("My new folder").click()
    page.get_by_test_id("contextTree").get_by_text("My Workspace").click()


def test_simple_workspace_workflow(
    logged_in_context, product_url, test_module_teardown
):
    page = logged_in_context.new_page()

    page.goto(f"{product_url}")
    page.wait_for_timeout(1000)
    page.get_by_text("Shared Workspaces").click()
