# pylint: disable=no-name-in-module
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect
from pydantic import AnyUrl


@pytest.fixture
def apps_metadata() -> dict:
    """Load the apps metadata JSON file."""
    metadata_path = (
        Path(__file__).parents[3]
        / "services"
        / "static-webserver"
        / "client"
        / "scripts"
        / "apps_metadata.json"
    )
    with metadata_path.open() as f:
        return json.load(f)


def test_site_metadata(page: Page, product_url: AnyUrl, apps_metadata: dict):
    """Check site metadata including title, description and Open Graph tags."""
    response = page.goto(f"{product_url}")
    assert response
    assert response.ok, response.body()
    # oSPARC ([0]) is the product served by default
    replacements = apps_metadata["applications"][0]["replacements"]

    # Check page title
    expect(page).to_have_title(re.compile(r".+PARC.+"))

    # Check description meta tag
    description_locator = page.locator("head > meta[name='description']")
    expect(description_locator).to_have_attribute(
        "content", replacements["replace_me_og_description"]
    )

    # Check Open Graph title
    og_title_locator = page.locator("head > meta[property='og:title']")
    expect(og_title_locator).to_have_attribute(
        "content", replacements["replace_me_og_title"]
    )

    # Check Open Graph description
    og_description_locator = page.locator("head > meta[property='og:description']")
    expect(og_description_locator).to_have_attribute(
        "content", replacements["replace_me_og_description"]
    )
