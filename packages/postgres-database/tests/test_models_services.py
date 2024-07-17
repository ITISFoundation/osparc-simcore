import pytest
from simcore_postgres_database.models.services_compatibility import (
    services_compatibility,
)

assert services_compatibility


def test_insert_services_compatibility():

    # services_meta_data
    # services_compatibility
    # TODO: use this test to produce complete fakes for other tests
    pytest.fail(reason="Not implemented")


def test_update_services_compatibility():
    # what can change and what not?
    pytest.fail(reason="Not implemented")


def test_delete_services_compatibility():
    # TODO: how it deletes? casacade/null policies?
    # TODO: pk dependencies?
    pytest.fail(reason="Not implemented")
