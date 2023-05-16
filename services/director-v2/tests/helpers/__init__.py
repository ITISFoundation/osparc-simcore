import pytest

# NOTE: this ensures that pytest rewrites the assertion so that comparison look nice in the console
pytest.register_assert_rewrite("helpers.shared_comp_utils")
