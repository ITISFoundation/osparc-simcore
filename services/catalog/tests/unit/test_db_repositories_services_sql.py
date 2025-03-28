# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from simcore_postgres_database.utils import as_postgres_sql_query_str
from simcore_service_catalog.db.repositories._services_sql import (
    AccessRightsClauses,
    can_get_service_stmt,
    get_service_history_stmt,
    get_service_stmt,
    latest_services_total_count_stmt,
    list_latest_services_stmt,
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
    user_id = 425  # 425 (guidon)  # 4 (odei)
    service_key = "simcore/services/comp/isolve"
    service_version = "2.0.85"

    service_key = "simcore/services/dynamic/raw-graphs"
    service_version = "2.11.2"

    service_key = "simcore/services/dynamic/s4l-core-8-0-0-dy"
    service_version = "3.2.39"

    _check(
        get_service_history_stmt,
        product_name=product_name,
        user_id=user_id,
        access_rights=AccessRightsClauses.can_read,
        service_key=service_key,
    )

    _check(
        can_get_service_stmt,
        product_name=product_name,
        user_id=user_id,
        access_rights=AccessRightsClauses.can_read,
        service_key=service_key,
        service_version=service_version,
    )

    _check(
        get_service_stmt,
        product_name=product_name,
        user_id=user_id,
        access_rights=AccessRightsClauses.can_read,
        service_key=service_key,
        service_version=service_version,
    )

    _check(
        list_latest_services_stmt,
        product_name=product_name,
        user_id=user_id,
        access_rights=AccessRightsClauses.can_read,
        limit=15,
        offset=80,
    )

    _check(
        latest_services_total_count_stmt,
        product_name=product_name,
        user_id=user_id,
        access_rights=AccessRightsClauses.can_read,
    )
