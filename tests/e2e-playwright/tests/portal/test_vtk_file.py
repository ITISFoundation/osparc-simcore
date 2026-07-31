# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import APIRequestContext, Page
from pytest_simcore.helpers.playwright import get_node_id_from_service_key, wait_for_service_running

_FILE_TYPE = "VTK"

# NOTE: port of the legacy VTK_file.js, which calls `waitForServices(..., waitForConnected=false)`
_IS_SERVICE_LEGACY = False


def _resolve_viewer_url(
    api_request_context: APIRequestContext,
    *,
    url_prefix: str,
    file_type: str,
    params: dict[str, str],
) -> str:
    """Resolves the public "study dispatcher" URL for a given file type, appending the
    provided query parameters (e.g. download_link, file_size).
    """
    response = api_request_context.get(f"{url_prefix}/v0/viewers/default")
    assert response.ok, f"{response.status}: {response.text()}"
    viewers = response.json()["data"]
    viewer = next(v for v in viewers if v["file_type"] == file_type)

    # NOTE: view_url already has its own query string (file_type, viewer_key, viewer_version),
    # so the extra params must be merged in rather than appended with a second '?'
    split_url = urlsplit(viewer["view_url"])
    merged_query = urlencode([*parse_qsl(split_url.query), *params.items()])
    return urlunsplit(split_url._replace(query=merged_query))


def test_vtk_file(
    page: Page,
    api_request_context: APIRequestContext,
    open_study_link: Callable[..., Any],
    viewer_url_prefix: str,
    download_link: str,
    file_size: str,
    service_start_timeout: int,
) -> None:
    url = _resolve_viewer_url(
        api_request_context,
        url_prefix=viewer_url_prefix,
        file_type=_FILE_TYPE,
        params={"download_link": download_link, "file_size": file_size},
    )

    opened_study = open_study_link(url)
    workbench = opened_study.project_data["workbench"]
    node_id = get_node_id_from_service_key(workbench, "3d-viewer-gpu")

    iframe_locator = wait_for_service_running(
        page=page,
        node_id=node_id,
        websocket=opened_study.websocket,
        timeout=service_start_timeout,
        press_start_button=False,
        product_url=opened_study.product_url,
        is_service_legacy=_IS_SERVICE_LEGACY,
    )

    # click on document icon on top
    iframe_locator.locator("xpath=/html/body/div/div/div[1]/div[1]/div[2]/div[1]/div[1]/i[2]").click()

    # then click on the file to render it
    iframe_locator.locator("xpath=/html/body/div/div/div[1]/div[1]/div[2]/div[2]/div/ul[2]").click()
