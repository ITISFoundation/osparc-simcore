# pytest_simcore.docker_compose fixture module config variables
import pytest

FIXTURE_CONFIG_CORE_SERVICES_SELECTION = "pytest_simcore_core_services_selection"
FIXTURE_CONFIG_OPS_SERVICES_SELECTION = "pytest_simcore_ops_services_selection"

# NOTE: this ensures that assertion printouts are nicely formated and complete see https://lorepirri.com/pytest-register-assert-rewrite.html
pytest.register_assert_rewrite("pytest_simcore.helpers")
