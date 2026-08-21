# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=no-name-in-module

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("oSparc e2e options", description="oSPARC-e2e specific parameters")
    group.addoption(
        "--mmux-num-sampling-points",
        action="store",
        type=int,
        default=None,
        help="Number of LHS sampling points for the RSM mmux e2e test (overrides the test's default)",
    )
