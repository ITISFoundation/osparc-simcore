import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup(
        "oSparc e2e options", description="oSPARC-e2e specific parameters"
    )
    group.addoption(
        "--broker-url",
        action="store",
        default=None,
        help="URL pointing to the deployment to be tested",
    )
    group.addoption(
        "--broker-username",
        action="store",
        default=None,
        help="User name for logging into the deployment",
    )
    group.addoption(
        "--broker-password",
        action="store",
        default=None,
        help="User name for logging into the deployment",
    )


@pytest.fixture()
def pact_broker_credentials(
    request: pytest.FixtureRequest,
):
    # Get credentials from either CLI arguments or environment variables
    broker_url = request.config.getoption("--broker-url", None) or os.getenv(
        "PACT_BROKER_URL"
    )
    broker_username = request.config.getoption("--broker-username", None) or os.getenv(
        "PACT_BROKER_USERNAME"
    )
    broker_password = request.config.getoption("--broker-password", None) or os.getenv(
        "PACT_BROKER_PASSWORD"
    )

    if not broker_username or not broker_password or not broker_url:
        pytest.fail(
            "Missing Pact Broker credentials. Set PACT_BROKER_USERNAME and PACT_BROKER_PASSWORD and PACT_BROKER_URL or pass them as CLI arguments."
        )

    return broker_url, broker_username, broker_password
