# pylint:disable=unrecognized-options

pytest_plugins = [
    "pytest_simcore.docker_api_proxy",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.repository_paths",
    "pytest_simcore.simcore_services",
]


def pytest_configure(config):
    # Set asyncio_mode to "auto"
    config.option.asyncio_mode = "auto"
