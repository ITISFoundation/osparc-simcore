import warnings

warnings.warn(
    f"{__name__} is deprecated for cookiecutter-osparc-service>0.4.Use directoy test CLI instead."
    "See https://github.com/ITISFoundation/cookiecutter-osparc-service/releases/tag/v0.4.0",
    DeprecationWarning,
)


def pytest_addoption(parser):
    group = parser.getgroup("service-integration")
    group.addoption(
        "--service-dir",
        action="store",
        help="Base directory for target service",
    )

    group.addoption(
        "--metadata",
        action="store",
        help="metadata yaml configuration file",
    )
