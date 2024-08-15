import logging
import shutil

import pytest

_logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    simcore_group = parser.getgroup("simcore")
    simcore_group.addoption(
        "--disk-usage", action="store_true", help="Enable disk usage monitoring"
    )
    simcore_group.addoption(
        "--disk-usage-threshold",
        action="store",
        type=float,
        default=0.0,
        help="Set the threshold for disk usage increase as a percentage. No warning if increase is below this percentage.",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Check if the disk usage monitoring is enabled and register the plugin."""
    if config.getoption("--disk-usage"):
        config.pluginmanager.register(DiskUsagePlugin(config), "disk_usage_plugin")


class DiskUsagePlugin:
    """
    The purpose of this plugin is to monitor disk usage during test execution, identifying tests
    that do not properly clean up resources. This helps prevent potential issues when running
    continuous integration (CI) pipelines on external systems, such as GitHub Actions.

    The plugin is activated by using the `--disk-usage` option, and
    it can be configured with a custom threshold using the `--disk-usage-threshold` option.

    Warnings are generated if disk usage increases beyond the specified threshold,
    allowing for targeted investigation of resource management
    in specific tests, modules, or the entire test session.

    As example, the CI in gh-actions reported this:
        XMinioStorageFull: Storage backend has reached its minimum free drive threshold. Please delete a few objects to proceed.
    """

    def __init__(self, config):
        self.threshold = config.getoption("--disk-usage-threshold")

    @staticmethod
    def _get_disk_usage():
        return shutil.disk_usage("/").used

    def _log_disk_usage_increase(
        self, initial_usage: int, final_usage: int, scope_name: str
    ):
        if final_usage > initial_usage:
            increase = final_usage - initial_usage
            increase_percent = (increase / initial_usage) * 100

            if increase_percent >= self.threshold:
                _logger.warning(
                    "Disk usage increased by %s bytes during %s.", increase, scope_name
                )

    @pytest.fixture(scope="session", autouse=True)
    def monitor_session_disk_usage(self):
        """SESSION-level fixture to monitor overall disk usage."""
        initial_usage = self._get_disk_usage()

        yield

        final_usage = self._get_disk_usage()
        self._log_disk_usage_increase(initial_usage, final_usage, "the session")

    @pytest.fixture(scope="module", autouse=True)
    def monitor_module_disk_usage(self, request):
        """MODULE-level fixture to monitor disk usage before and after each module."""
        initial_usage = self._get_disk_usage()

        yield

        final_usage = self._get_disk_usage()
        module_name = request.module.__name__
        self._log_disk_usage_increase(
            initial_usage, final_usage, f"the module {module_name}"
        )

    @pytest.fixture(autouse=True)
    def monitor_test_disk_usage(self, request):
        """FUNCTION-level fixture to monitor disk usage before and after each test."""
        initial_usage = self._get_disk_usage()

        yield

        final_usage = self._get_disk_usage()
        test_name = request.node.name
        self._log_disk_usage_increase(
            initial_usage, final_usage, f"the test {test_name}"
        )
