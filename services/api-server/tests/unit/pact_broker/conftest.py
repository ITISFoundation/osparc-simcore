import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup(
        "Pact broker contract test",
        description="Pact broker contract test specific parameters",
    )
    group.addoption(
        "--pact-broker-url",
        action="store",
        default=None,
        help="URL pointing to the deployment to be tested",
    )
    group.addoption(
        "--pact-broker-username",
        action="store",
        default=None,
        help="User name for logging into the deployment",
    )
    group.addoption(
        "--pact-broker-password",
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

    # Identify missing credentials
    missing = [
        name
        for name, value in {
            "PACT_BROKER_URL": broker_url,
            "PACT_BROKER_USERNAME": broker_username,
            "PACT_BROKER_PASSWORD": broker_password,
        }.items()
        if not value
    ]

    if missing:
        pytest.fail(
            f"Missing Pact Broker credentials: {', '.join(missing)}. Set them as environment variables or pass them as CLI arguments."
        )

    return broker_url, broker_username, broker_password
