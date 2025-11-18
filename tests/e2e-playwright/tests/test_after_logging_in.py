import pytest
from playwright.sync_api import Page
from pydantic import AnyUrl
from pytest_simcore.helpers.playwright import (
    RobustWebSocket,
)


def test_profile_response(
    page: Page,
    log_in_and_out: RobustWebSocket,
    product_url: AnyUrl,
    user_name: str,
):
    """Test profile endpoint response after logging in."""
    # Navigate to trigger API calls
    with page.expect_response("**/me") as response:
        page.goto(f"{product_url}")
    assert response
    assert response.value.ok, response.value.body()
    response_dict = response.value.json()
    assert "data" in response_dict, "Expected 'data' in profile response"
    assert "login" in response_dict["data"], "Expected 'login' in profile data"
    assert (
        response_dict["data"]["login"] == user_name
    ), "Logged in username does not match"


def test_tags_response(
    page: Page,
    log_in_and_out: RobustWebSocket,
    product_url: AnyUrl,
):
    """Test tags endpoint response after logging in."""
    with page.expect_response("**/tags") as response:
        page.goto(f"{product_url}")
    assert response
    assert response.value.ok, response.value.body()

    response_dict = response.value.json()
    assert "data" in response_dict, "Expected 'data' in tags response"
    tags_data = response_dict["data"]
    assert isinstance(tags_data, list)


def test_ui_config_response(
    page: Page,
    log_in_and_out: RobustWebSocket,
    product_url: AnyUrl,
):
    """Test UI config endpoint response after logging in."""
    with page.expect_response("**/ui") as response:
        page.goto(f"{product_url}")
    assert response
    assert response.value.ok, response.value.body()

    response_dict = response.value.json()
    assert "data" in response_dict, "Expected 'data' in ui response"

    ui_data = response_dict["data"]
    assert ui_data["productName"] == "osparc"

    ui_config = ui_data["ui"]
    assert isinstance(ui_config, dict)
    assert ui_config is not None


@pytest.mark.parametrize("study_type", ["user", "template"])
def test_studies_response(
    page: Page,
    log_in_and_out: RobustWebSocket,
    product_url: AnyUrl,
    study_type: str,
):
    """Test studies endpoint response after logging in."""
    with page.expect_response(f"**/projects?type={study_type}*") as response:
        page.goto(f"{product_url}")
    assert response
    assert response.value.ok, response.value.body()

    response_dict = response.value.json()
    assert "data" in response_dict, "Expected 'data' in projects response"
    studies_data = response_dict["data"]
    assert isinstance(studies_data, list)


def test_services_response(
    page: Page,
    log_in_and_out: RobustWebSocket,
    product_url: AnyUrl,
):
    """Test services catalog endpoint response after logging in."""
    with page.expect_response("**/catalog/services/-/latest*") as response:
        page.goto(f"{product_url}")
    assert response
    assert response.value.ok, response.value.body()

    response_dict = response.value.json()

    services_data = response_dict["data"]
    assert services_data["_meta"]["total"] > 0
    assert isinstance(services_data["data"], list)
    assert len(services_data["data"]) > 0
