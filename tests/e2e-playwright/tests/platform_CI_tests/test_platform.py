# pylint: disable=no-name-in-module
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Iterable
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect
from playwright.sync_api._generated import BrowserContext, Playwright
from pydantic import AnyUrl
from pytest_simcore.helpers.playwright import SECOND


@pytest.fixture(scope="session")
def store_browser_context() -> bool:
    return True


@pytest.fixture
def logged_in_context(
    playwright: Playwright,
    store_browser_context: bool,
    request: pytest.FixtureRequest,
    pytestconfig: pytest.Config,
    results_path: Path,
) -> Iterable[BrowserContext]:
    is_headed = "--headed" in pytestconfig.invocation_params.args

    file_path = Path("state.json")
    if not file_path.exists():
        request.getfixturevalue("log_in_and_out")

    browser = playwright.chromium.launch(headless=not is_headed)
    context = browser.new_context(storage_state="state.json")
    test_name = request.node.name
    context.tracing.start(
        title=f"Trace for Browser 2 in test {test_name}",
        snapshots=True,
        screenshots=True,
    )
    yield context
    context.tracing.stop(path=f"{results_path}/second_browser_trace.zip")
    context.close()
    browser.close()


@pytest.fixture(scope="module")
def test_module_teardown() -> Iterable[None]:
    yield  # Run the tests

    file_path = Path("state.json")
    if file_path.exists():
        file_path.unlink()


def test_simple_folder_workflow(logged_in_context: BrowserContext, product_url: AnyUrl, test_module_teardown: None):
    page = logged_in_context.new_page()

    page.goto(f"{product_url}")
    page.wait_for_timeout(1 * SECOND)
    page.get_by_test_id("newPlusBtn").click()
    page.get_by_test_id("newFolderButton").click()

    with page.expect_response(
        lambda response: "folders" in response.url and response.status == 201 and response.request.method == "POST"
    ) as response_info:
        page.get_by_test_id("folderEditorTitle").fill("My new folder")
        page.get_by_test_id("folderEditorCreate").click()

    _folder_id = response_info.value.json()["data"]["folderId"]
    page.get_by_test_id(f"folderItem_{_folder_id}").click()
    page.get_by_test_id("workspacesAndFoldersTreeItem_null_null").click()


def test_simple_workspace_workflow(logged_in_context: BrowserContext, product_url: AnyUrl, test_module_teardown: None):
    page = logged_in_context.new_page()

    page.goto(f"{product_url}")
    page.wait_for_timeout(1 * SECOND)
    page.get_by_test_id("workspacesAndFoldersTreeItem_-1_null").click()

    with page.expect_response(
        lambda response: "workspaces" in response.url and response.status == 201 and response.request.method == "POST"
    ) as response_info:
        page.get_by_test_id("newWorkspaceButton").click()

        workspace_title_field = page.get_by_test_id("workspaceEditorTitle")
        # wait until the title is automatically filled up
        expect(workspace_title_field).not_to_have_value("")
        page.get_by_test_id("workspaceEditorSave").click()

    _workspace_id = response_info.value.json()["data"]["workspaceId"]
    page.get_by_test_id(f"workspaceItem_{_workspace_id}").click()
    page.get_by_test_id("workspacesAndFoldersTreeItem_null_null").click()


@pytest.mark.parametrize(
    "path, expected_og_title",
    [
        ("/", "oSPARC"),
        ("/s4l/index.html", "Sim4Life"),
        ("/tis/index.html", "TI Plan - IT'IS"),
    ],
)
def test_product_frontend_app_served(page: Page, path: str, product_url: AnyUrl, expected_og_title: str):
    response = page.goto(f"{product_url}{path}")
    page.wait_for_timeout(1 * SECOND)
    assert response
    assert response.ok, response.body()

    locator = page.locator("meta[property='og:title']")
    expect(locator).to_be_attached(timeout=1 * SECOND)

    if expected_og_title is not None:
        expect(locator).to_have_attribute("content", expected_og_title, timeout=1 * SECOND)
