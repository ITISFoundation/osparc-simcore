# pylint: disable=no-name-in-module
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest
from playwright.sync_api import Page, Response
from pytest_simcore.helpers.playwright import RobustWebSocket


@pytest.fixture
def response_collector(page: Page) -> list[dict[str, Any]]:
    responses: list[dict[str, Any]] = []

    def handle_response(response: Response) -> None:
        if (
            response.ok
            and "application/json" in response.headers.get("content-type", "")
            and response.body()
        ):
            responses.append(
                {
                    "url": response.url,
                    "json": response.json(),
                }
            )

    page.on("response", handle_response)
    return responses


def test_all_endpoints_after_login(
    user_name: str,
    response_collector: list[dict[str, Any]],
    log_in_and_out: RobustWebSocket,
):
    """This test mimicks what the old pupeteer tests were doing in tests/e2e/tests"""
    # Profile
    response = next((r for r in response_collector if "/me" in r["url"]), None)
    assert response is not None
    response_dict = response["json"]

    assert "data" in response_dict, "Expected 'data' in profile response"
    assert "login" in response_dict["data"], "Expected 'login' in profile data"
    assert (
        response_dict["data"]["login"] == user_name
    ), "Logged in username does not match"

    # Tags
    response = next((r for r in response_collector if "/tags" in r["url"]), None)
    assert response is not None
    response_dict = response["json"]

    assert "data" in response_dict, "Expected 'data' in tags response"
    tags_data = response_dict["data"]
    assert isinstance(tags_data, list)

    # UI config
    response = next((r for r in response_collector if "/ui" in r["url"]), None)
    assert response is not None
    response_dict = response["json"]

    assert "data" in response_dict, "Expected 'data' in ui response"
    ui_data = response_dict["data"]
    assert ui_data["productName"] == "osparc"

    ui_config = ui_data["ui"]
    assert isinstance(ui_config, dict)
    assert ui_config is not None

    # Studies (user and template)
    for study_type in ["user", "template"]:
        response = next(
            (
                r
                for r in response_collector
                if f"/projects?type={study_type}" in r["url"]
            ),
            None,
        )
        assert response is not None
        response_dict = response["json"]

        assert "data" in response_dict, "Expected 'data' in projects response"
        studies_data = response_dict["data"]
        assert isinstance(studies_data, list)

    # Services
    response = next(
        (r for r in response_collector if "/catalog/services/-/latest" in r["url"]),
        None,
    )
    assert response is not None
    response_dict = response["json"]

    services_data = response_dict["data"]
    assert services_data["_meta"]["total"] > 0
    assert isinstance(services_data["data"], list)
    assert len(services_data["data"]) > 0
