import playwright
import pytest


@pytest.fixture
def osparc_test_id_attribute(playwright):
    # Set a custom test id attribute
    playwright.selectors.set_test_id_attribute("osparc-test-id")
