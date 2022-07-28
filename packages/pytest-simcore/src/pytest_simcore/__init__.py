# Collection of tests fixtures for integration testing
import pkg_resources

__version__: str = pkg_resources.get_distribution("pytest-simcore").version


def pytest_addoption(parser):
    group = parser.getgroup("simcore")
    group.addoption(
        "--keep-docker-up",
        action="store_true",
        default=False,
        help="Keep stack/registry up after fixtures closes",
    )

    # DUMMY
    parser.addini("HELLO", "Dummy pytest.ini setting")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "heavy_load: mark test that uses huge amount of data"
    )
