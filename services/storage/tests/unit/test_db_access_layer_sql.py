# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from faker import Faker
from simcore_postgres_database.utils import as_postgres_sql_query_str
from simcore_service_storage.db_access_layer import _get_project_access_rights_stmt


def test_build_access_rights_sql_statements(faker: Faker):
    def _check(func_smt, **kwargs):
        print()
        print(f"{func_smt.__name__:*^100}")
        stmt = func_smt(**kwargs)
        print()
        print(as_postgres_sql_query_str(stmt))
        print()

    _check(
        _get_project_access_rights_stmt,
        user_id=42,
        project_id=faker.uuid4(),
    )
