# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from simcore_postgres_database.utils import as_postgres_sql_query_str
from simcore_service_catalog.db.repositories._services_sql import (
    AccessRightsClauses,
    batch_get_services_stmt,
    get_service_with_history_stmt,
    list_latest_services_with_history_stmt,
    list_services_stmt2,
    list_services_with_history_stmt,
    total_count_stmt,
)


def test_building_services_sql_statements():
    def _check(func_smt, **kwargs):
        print(f"{func_smt.__name__:*^100}")
        stmt = func_smt(**kwargs)
        print()
        print(as_postgres_sql_query_str(stmt))
        print()

    # some data
    product_name = "osparc"
    user_id = 4

    _check(
        get_service_with_history_stmt,
        product_name=product_name,
        user_id=user_id,
        access_rights=AccessRightsClauses.can_read,
        service_key="simcore/services/comp/kember-cardiac-model",
        service_version="1.0.0",
    )

    _check(
        list_latest_services_with_history_stmt,
        product_name=product_name,
        user_id=user_id,
        access_rights=AccessRightsClauses.can_read,
        limit=10,
        offset=None,
    )

    _check(
        total_count_stmt,
        product_name=product_name,
        user_id=user_id,
        access_rights=AccessRightsClauses.can_read,
    )

    _check(
        list_services_with_history_stmt,
        product_name=product_name,
        user_id=user_id,
        access_rights=AccessRightsClauses.can_read,
        limit=10,
        offset=None,
    )

    _check(
        batch_get_services_stmt,
        product_name=product_name,
        selection=[
            ("simcore/services/comp/kember-cardiac-model", "1.0.0"),
            ("simcore/services/comp/human-gb-0d-cardiac-model", "1.0.0"),
            ("simcore/services/dynamic/invalid", "2.0.0"),
        ],
    )

    _check(list_services_stmt2)
