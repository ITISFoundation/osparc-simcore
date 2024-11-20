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
    playwright,
    store_browser_context: bool,
    request: pytest.FixtureRequest,
    pytestconfig,
):
    is_headed = "--headed" in pytestconfig.invocation_params.args

    file_path = Path("state.json")
    if not file_path.exists():
        request.getfixturevalue("log_in_and_out")

    browser = playwright.chromium.launch(headless=not is_headed)
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
    logged_in_context, product_url, test_module_teardown
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
        page.get_by_test_id("workspaceEditorSave").click()
    _workspace_id = response_info.value.json()["data"]["workspaceId"]
    page.get_by_test_id(f"workspaceItem_{_workspace_id}").click()
    page.get_by_test_id("workspacesAndFoldersTreeItem_null_null").click()
