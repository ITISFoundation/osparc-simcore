# pylint: disable=no-name-in-module
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path
from typing import Iterable

import pytest
from playwright.sync_api._generated import BrowserContext, Playwright, expect
from pydantic import AnyUrl


@pytest.fixture(scope="session")
def store_browser_context() -> bool:
    return True


@pytest.fixture
def results_path(request):
    """
    Fixture to retrieve the path to the test's results directory.
    """
    # Check if `results_dir` is available in the current test's user properties
    results_dir = dict(request.node.user_properties).get("results_dir")
    if not results_dir:
        results_dir = "test-results"  # Default results directory
    test_name = request.node.name
    test_dir = Path(results_dir) / test_name
    test_dir.mkdir(parents=True, exist_ok=True)  # Ensure the test directory exists
    return test_dir


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


def test_simple_folder_workflow(
    logged_in_context: BrowserContext, product_url: AnyUrl, test_module_teardown: None
):
    page = logged_in_context.new_page()

    page.goto(f"{product_url}")
    page.wait_for_timeout(1000)
    page.get_by_test_id("newFolderButton").click()

    with page.expect_response(
        lambda response: "folders" in response.url
        and response.status == 201
        and response.request.method == "POST"
    ) as response_info:
        page.get_by_test_id("folderEditorTitle").fill("My new folder")
        page.get_by_test_id("folderEditorCreate").click()

    _folder_id = response_info.value.json()["data"]["folderId"]
    page.get_by_test_id(f"folderItem_{_folder_id}").click()
    page.get_by_test_id("workspacesAndFoldersTreeItem_null_null").click()


def test_simple_workspace_workflow(
    logged_in_context: BrowserContext, product_url: AnyUrl, test_module_teardown: None
):
    page = logged_in_context.new_page()

    page.goto(f"{product_url}")
    page.wait_for_timeout(1000)
    page.get_by_test_id("workspacesAndFoldersTreeItem_-1_null").click()

    with page.expect_response(
        lambda response: "workspaces" in response.url
        and response.status == 201
        and response.request.method == "POST"
    ) as response_info:
        page.get_by_test_id("newWorkspaceButton").click()

        workspace_title_field = page.get_by_test_id("workspaceEditorTitle")
        # wait until the title is automatically filled up
        expect(workspace_title_field).not_to_have_value("")
        page.get_by_test_id("workspaceEditorSave").click()

    _workspace_id = response_info.value.json()["data"]["workspaceId"]
    page.get_by_test_id(f"workspaceItem_{_workspace_id}").click()
    page.get_by_test_id("workspacesAndFoldersTreeItem_null_null").click()
