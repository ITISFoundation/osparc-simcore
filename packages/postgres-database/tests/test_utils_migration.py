# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from alembic.script.revision import MultipleHeads
from simcore_postgres_database.utils_migration import get_current_head


def test_migration_has_no_branches():
    try:
        current_head = get_current_head()
        assert current_head
        assert isinstance(current_head, str)
    except MultipleHeads as err:
        pytest.fail(
            f"This project migration expected a single head (i.e. no branches): {err}"
        )
