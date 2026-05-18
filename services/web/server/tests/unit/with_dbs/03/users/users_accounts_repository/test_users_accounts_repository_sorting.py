# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from aiohttp import web
from common_library.users_enums import AccountRequestStatus
from models_library.list_operations import OrderClause, OrderDirection
from models_library.products import ProductName
from pytest_simcore.helpers.webserver_users import SortingUserTestData
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.users import _accounts_repository


async def test_list_merged_users_sorting_default(
    app: web.Application,
    product_name: ProductName,
    sorting_user_data: SortingUserTestData,
):
    """When no sort_by is provided, results should be ordered by email ASC (the default)."""
    asyncpg_engine = get_asyncpg_engine(app)

    users_list, _ = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_any_account_request_status=[AccountRequestStatus.PENDING],
        filter_include_deleted=False,
        # sort_by omitted: should use default email ASC
    )

    test_emails = {"alpha@example.com", "middle@example.com", "zeta@example.com"}
    found_emails = [user["email"] for user in users_list if user["email"] in test_emails]

    # Default is email ASC
    assert found_emails == sorted(found_emails), "Default ordering should be email ASC"
    assert found_emails == ["alpha@example.com", "middle@example.com", "zeta@example.com"]


async def test_list_merged_users_sorting_single_field_asc(
    app: web.Application,
    product_name: ProductName,
    sorting_user_data: SortingUserTestData,
):
    """Sort by first_name ASC: Alice < Bob < Zoe."""
    asyncpg_engine = get_asyncpg_engine(app)

    users_list, _ = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_any_account_request_status=[AccountRequestStatus.PENDING],
        filter_include_deleted=False,
        sort_by=[OrderClause(field="first_name", direction=OrderDirection.ASC)],
    )

    found_emails = [user["email"] for user in users_list if user["email"] in sorting_user_data.emails_by_name_asc]

    # Alice(zeta@) < Bob(middle@) < Zoe(alpha@)
    assert found_emails == sorting_user_data.emails_by_name_asc


async def test_list_merged_users_sorting_single_field_desc(
    app: web.Application,
    product_name: ProductName,
    sorting_user_data: SortingUserTestData,
):
    """Sort by email DESC: zeta > middle > alpha."""
    asyncpg_engine = get_asyncpg_engine(app)

    users_list, _ = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_any_account_request_status=[AccountRequestStatus.PENDING],
        filter_include_deleted=False,
        sort_by=[OrderClause(field="email", direction=OrderDirection.DESC)],
    )

    test_emails = {"alpha@example.com", "middle@example.com", "zeta@example.com"}
    found_emails = [user["email"] for user in users_list if user["email"] in test_emails]

    assert found_emails == ["zeta@example.com", "middle@example.com", "alpha@example.com"]


async def test_list_merged_users_sorting_multiple_fields(
    app: web.Application,
    product_name: ProductName,
    sorting_user_data: SortingUserTestData,
):
    """Sort by status ASC then email DESC — all same status, so email DESC is the tiebreaker."""
    asyncpg_engine = get_asyncpg_engine(app)

    users_list, _ = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_any_account_request_status=[AccountRequestStatus.PENDING],
        filter_include_deleted=False,
        sort_by=[
            OrderClause(field="status", direction=OrderDirection.ASC),
            OrderClause(field="email", direction=OrderDirection.DESC),
        ],
    )

    test_emails = {"alpha@example.com", "middle@example.com", "zeta@example.com"}
    found_emails = [user["email"] for user in users_list if user["email"] in test_emails]

    # All PENDING (same status), so secondary sort email DESC applies
    assert found_emails == ["zeta@example.com", "middle@example.com", "alpha@example.com"]


async def test_list_merged_users_sorting_by_name_differs_from_email(
    app: web.Application,
    product_name: ProductName,
    sorting_user_data: SortingUserTestData,
):
    """Sorting by first_name produces a different order than sorting by email."""
    asyncpg_engine = get_asyncpg_engine(app)

    users_by_name, _ = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_any_account_request_status=[AccountRequestStatus.PENDING],
        filter_include_deleted=False,
        sort_by=[OrderClause(field="first_name", direction=OrderDirection.ASC)],
    )
    users_by_email, _ = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_any_account_request_status=[AccountRequestStatus.PENDING],
        filter_include_deleted=False,
        sort_by=[OrderClause(field="email", direction=OrderDirection.ASC)],
    )

    emails_by_name = [user["email"] for user in users_by_name if user["email"] in sorting_user_data.emails_by_name_asc]
    emails_by_email = [
        user["email"] for user in users_by_email if user["email"] in sorting_user_data.emails_by_name_asc
    ]

    assert emails_by_name == sorting_user_data.emails_by_name_asc
    assert emails_by_email == sorted(sorting_user_data.emails_by_name_asc)
    assert emails_by_name != emails_by_email
