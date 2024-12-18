from pathlib import Path

import pytest


@pytest.fixture
def results_path(request):
    """
    Fixture to retrieve the path to the test's results directory.
    """
    # Check if `results_dir` is available in the current test's user properties
    results_dir = dict(request.node.user_properties).get("results_dir")
    if not results_dir:
        results_dir = "test-results"  # Default results directory
    test_name = request.node.name
    test_dir = Path(results_dir) / test_name
    test_dir.mkdir(parents=True, exist_ok=True)  # Ensure the test directory exists
    return test_dir
