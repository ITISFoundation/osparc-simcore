# pylint: disable=unused-import

pytest_plugins = "pytester"


try:
    import pytest_sugar

    raise Exception(
        "Cannot run these tests with this module installed: "
        "pip uninstall pytest_sugar"
    )
except ImportError:
    # GOOD
    pass
