import logging
from datetime import datetime

# pylint: disable=too-many-arguments
from decimal import Decimal
from typing import cast

import sqlalchemy as sa
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    WalletTotalCredits,
)
from models_library.api_schemas_storage import S3BucketName
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.resource_tracker import (
    CreditClassification,
    CreditTransactionStatus,
    ServiceRunStatus,
)
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import PositiveInt
from simcore_postgres_database.models.projects_tags import projects_tags
from simcore_postgres_database.models.resource_tracker_credit_transactions import (
    resource_tracker_credit_transactions,
)
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
)
from simcore_postgres_database.models.tags import tags
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ....exceptions.errors import ServiceRunNotCreatedDBError
from ....models.service_runs import (
    OsparcCreditsAggregatedByServiceKeyDB,
    ServiceRunCreate,
    ServiceRunDB,
    ServiceRunForCheckDB,
    ServiceRunLastHeartbeatUpdate,
    ServiceRunStoppedAtUpdate,
    ServiceRunWithCreditsDB,
)

_logger = logging.getLogger(__name__)


async def create_service_run(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    data: ServiceRunCreate,
) -> ServiceRunID:
    async with transaction_context(engine, connection) as conn:
        insert_stmt = (
            resource_tracker_service_runs.insert()
            .values(
                product_name=data.product_name,
                service_run_id=data.service_run_id,
                wallet_id=data.wallet_id,
                wallet_name=data.wallet_name,
                pricing_plan_id=data.pricing_plan_id,
                pricing_unit_id=data.pricing_unit_id,
                pricing_unit_cost_id=data.pricing_unit_cost_id,
                pricing_unit_cost=data.pricing_unit_cost,
                simcore_user_agent=data.simcore_user_agent,
                user_id=data.user_id,
                user_email=data.user_email,
                project_id=f"{data.project_id}",
                project_name=data.project_name,
                node_id=f"{data.node_id}",
                node_name=data.node_name,
                parent_project_id=f"{data.parent_project_id}",
                root_parent_project_id=f"{data.root_parent_project_id}",
                root_parent_project_name=data.root_parent_project_name,
                parent_node_id=f"{data.parent_node_id}",
                root_parent_node_id=f"{data.root_parent_node_id}",
                service_key=data.service_key,
                service_version=data.service_version,
                service_type=data.service_type,
                service_resources=data.service_resources,
                service_additional_metadata=data.service_additional_metadata,
                started_at=data.started_at,
                stopped_at=None,
                service_run_status=ServiceRunStatus.RUNNING,
                modified=sa.func.now(),
                last_heartbeat_at=data.last_heartbeat_at,
            )
            .returning(resource_tracker_service_runs.c.service_run_id)
        )
        result = await conn.execute(insert_stmt)
    row = result.first()
    if row is None:
        raise ServiceRunNotCreatedDBError(data=data)
    return cast(ServiceRunID, row[0])


async def update_service_run_last_heartbeat(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    data: ServiceRunLastHeartbeatUpdate,
) -> ServiceRunDB | None:
    async with transaction_context(engine, connection) as conn:
        update_stmt = (
            resource_tracker_service_runs.update()
            .values(
                modified=sa.func.now(),
                last_heartbeat_at=data.last_heartbeat_at,
                missed_heartbeat_counter=0,
            )
            .where(
                (resource_tracker_service_runs.c.service_run_id == data.service_run_id)
                & (
                    resource_tracker_service_runs.c.service_run_status
                    == ServiceRunStatus.RUNNING
                )
                & (
                    resource_tracker_service_runs.c.last_heartbeat_at
                    <= data.last_heartbeat_at
                )
            )
            .returning(sa.literal_column("*"))
        )
        result = await conn.execute(update_stmt)
    row = result.first()
    if row is None:
        return None
    return ServiceRunDB.model_validate(row)


async def update_service_run_stopped_at(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    data: ServiceRunStoppedAtUpdate,
) -> ServiceRunDB | None:
    async with transaction_context(engine, connection) as conn:
        update_stmt = (
            resource_tracker_service_runs.update()
            .values(
                modified=sa.func.now(),
                stopped_at=data.stopped_at,
                service_run_status=data.service_run_status,
                service_run_status_msg=data.service_run_status_msg,
            )
            .where(
                (resource_tracker_service_runs.c.service_run_id == data.service_run_id)
                & (
                    resource_tracker_service_runs.c.service_run_status
                    == ServiceRunStatus.RUNNING
                )
            )
            .returning(sa.literal_column("*"))
        )
        result = await conn.execute(update_stmt)
    row = result.first()
    if row is None:
        return None
    return ServiceRunDB.model_validate(row)


async def get_service_run_by_id(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    service_run_id: ServiceRunID,
) -> ServiceRunDB | None:
    async with pass_or_acquire_connection(engine, connection) as conn:
        stmt = sa.select(resource_tracker_service_runs).where(
            resource_tracker_service_runs.c.service_run_id == service_run_id
        )
        result = await conn.execute(stmt)
    row = result.first()
    if row is None:
        return None
    return ServiceRunDB.model_validate(row)


_project_tags_subquery = (
    sa.select(
        projects_tags.c.project_uuid_for_rut,
        sa.func.array_agg(tags.c.name).label("project_tags"),
    )
    .select_from(projects_tags.join(tags, projects_tags.c.tag_id == tags.c.id))
    .group_by(projects_tags.c.project_uuid_for_rut)
).subquery("project_tags_subquery")


async def list_service_runs_by_product_and_user_and_wallet(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    user_id: UserID | None,
    wallet_id: WalletID | None,
    # attribute filtering
    service_run_status: ServiceRunStatus | None = None,
    started_from: datetime | None = None,
    started_until: datetime | None = None,
    transaction_status: CreditTransactionStatus | None = None,
    project_id: ProjectID | None = None,
    # pagination
    offset: int,
    limit: int,
    # ordering
    order_by: OrderBy | None = None,
) -> tuple[int, list[ServiceRunWithCreditsDB]]:
    async with pass_or_acquire_connection(engine, connection) as conn:
        base_query = (
            sa.select(
                resource_tracker_service_runs.c.product_name,
                resource_tracker_service_runs.c.service_run_id,
                resource_tracker_service_runs.c.wallet_id,
                resource_tracker_service_runs.c.wallet_name,
                resource_tracker_service_runs.c.pricing_plan_id,
                resource_tracker_service_runs.c.pricing_unit_id,
                resource_tracker_service_runs.c.pricing_unit_cost_id,
                resource_tracker_service_runs.c.pricing_unit_cost,
                resource_tracker_service_runs.c.user_id,
                resource_tracker_service_runs.c.user_email,
                resource_tracker_service_runs.c.project_id,
                resource_tracker_service_runs.c.project_name,
                resource_tracker_service_runs.c.node_id,
                resource_tracker_service_runs.c.node_name,
                resource_tracker_service_runs.c.parent_project_id,
                resource_tracker_service_runs.c.root_parent_project_id,
                resource_tracker_service_runs.c.root_parent_project_name,
                resource_tracker_service_runs.c.parent_node_id,
                resource_tracker_service_runs.c.root_parent_node_id,
                resource_tracker_service_runs.c.service_key,
                resource_tracker_service_runs.c.service_version,
                resource_tracker_service_runs.c.service_type,
                resource_tracker_service_runs.c.service_resources,
                resource_tracker_service_runs.c.started_at,
                resource_tracker_service_runs.c.stopped_at,
                resource_tracker_service_runs.c.service_run_status,
                resource_tracker_service_runs.c.modified,
                resource_tracker_service_runs.c.last_heartbeat_at,
                resource_tracker_service_runs.c.service_run_status_msg,
                resource_tracker_service_runs.c.missed_heartbeat_counter,
                resource_tracker_credit_transactions.c.osparc_credits,
                resource_tracker_credit_transactions.c.transaction_status,
                sa.func.coalesce(
                    _project_tags_subquery.c.project_tags,
                    sa.cast(sa.text("'{}'"), sa.ARRAY(sa.String)),
                ).label("project_tags"),
            )
            .select_from(
                resource_tracker_service_runs.join(
                    resource_tracker_credit_transactions,
                    (
                        resource_tracker_service_runs.c.product_name
                        == resource_tracker_credit_transactions.c.product_name
                    )
                    & (
                        resource_tracker_service_runs.c.service_run_id
                        == resource_tracker_credit_transactions.c.service_run_id
                    ),
                    isouter=True,
                ).join(
                    _project_tags_subquery,
                    resource_tracker_service_runs.c.project_id
                    == _project_tags_subquery.c.project_uuid_for_rut,
                    isouter=True,
                )
            )
            .where(resource_tracker_service_runs.c.product_name == product_name)
        )

        if user_id:
            base_query = base_query.where(
                resource_tracker_service_runs.c.user_id == user_id
            )
        if wallet_id:
            base_query = base_query.where(
                resource_tracker_service_runs.c.wallet_id == wallet_id
            )
        if service_run_status:
            base_query = base_query.where(
                resource_tracker_service_runs.c.service_run_status == service_run_status
            )
        if started_from:
            base_query = base_query.where(
                sa.func.DATE(resource_tracker_service_runs.c.started_at)
                >= started_from.date()
            )
        if started_until:
            base_query = base_query.where(
                sa.func.DATE(resource_tracker_service_runs.c.started_at)
                <= started_until.date()
            )
        if project_id:
            base_query = base_query.where(
                resource_tracker_service_runs.c.project_id == project_id
            )
        if transaction_status:
            base_query = base_query.where(
                resource_tracker_credit_transactions.c.transaction_status
                == transaction_status
            )

        # Select total count from base_query
        subquery = base_query.subquery()
        count_query = sa.select(sa.func.count()).select_from(subquery)

        if order_by:
            if order_by.direction == OrderDirection.ASC:
                list_query = base_query.order_by(sa.asc(order_by.field))
            else:
                list_query = base_query.order_by(sa.desc(order_by.field))
        else:
            # Default ordering
            list_query = base_query.order_by(
                resource_tracker_service_runs.c.started_at.desc()
            )

        total_count = await conn.scalar(count_query)
        if total_count is None:
            total_count = 0

        result = await conn.stream(list_query.offset(offset).limit(limit))
        items: list[ServiceRunWithCreditsDB] = [
            ServiceRunWithCreditsDB.model_validate(row) async for row in result
        ]

        return cast(int, total_count), items


async def get_osparc_credits_aggregated_by_service(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    user_id: UserID | None,
    wallet_id: WalletID,
    offset: int,
    limit: int,
    started_from: datetime | None = None,
    started_until: datetime | None = None,
) -> tuple[int, list[OsparcCreditsAggregatedByServiceKeyDB]]:
    async with pass_or_acquire_connection(engine, connection) as conn:
        base_query = (
            sa.select(
                resource_tracker_service_runs.c.service_key,
                sa.func.SUM(
                    resource_tracker_credit_transactions.c.osparc_credits
                ).label("osparc_credits"),
                sa.func.SUM(
                    sa.func.round(
                        (
                            sa.func.extract(
                                "epoch",
                                resource_tracker_service_runs.c.stopped_at,
                            )
                            - sa.func.extract(
                                "epoch",
                                resource_tracker_service_runs.c.started_at,
                            )
                        )
                        / 3600,
                        2,
                    )
                ).label("running_time_in_hours"),
            )
            .select_from(
                resource_tracker_service_runs.join(
                    resource_tracker_credit_transactions,
                    (
                        resource_tracker_service_runs.c.product_name
                        == resource_tracker_credit_transactions.c.product_name
                    )
                    & (
                        resource_tracker_service_runs.c.service_run_id
                        == resource_tracker_credit_transactions.c.service_run_id
                    ),
                    isouter=True,
                )
            )
            .where(
                (resource_tracker_service_runs.c.product_name == product_name)
                & (
                    resource_tracker_credit_transactions.c.transaction_status.in_(
                        [
                            CreditTransactionStatus.BILLED,
                            CreditTransactionStatus.IN_DEBT,
                        ]
                    )
                )
                & (
                    resource_tracker_credit_transactions.c.transaction_classification
                    == CreditClassification.DEDUCT_SERVICE_RUN
                )
                & (resource_tracker_credit_transactions.c.wallet_id == wallet_id)
            )
            .group_by(resource_tracker_service_runs.c.service_key)
        )

        if user_id:
            base_query = base_query.where(
                resource_tracker_service_runs.c.user_id == user_id
            )
        if started_from:
            base_query = base_query.where(
                sa.func.DATE(resource_tracker_service_runs.c.started_at)
                >= started_from.date()
            )
        if started_until:
            base_query = base_query.where(
                sa.func.DATE(resource_tracker_service_runs.c.started_at)
                <= started_until.date()
            )

        subquery = base_query.subquery()
        count_query = sa.select(sa.func.count()).select_from(subquery)
        count_result = await conn.scalar(count_query)
        if count_result is None:
            count_result = 0

        # Default ordering and pagination
        list_query = (
            base_query.order_by(resource_tracker_service_runs.c.service_key.asc())
            .offset(offset)
            .limit(limit)
        )
        list_result = await conn.execute(list_query)

    return (
        cast(int, count_result),
        [
            OsparcCreditsAggregatedByServiceKeyDB.model_validate(row)
            for row in list_result.fetchall()
        ],
    )


async def sum_project_wallet_total_credits(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    wallet_id: WalletID,
    project_id: ProjectID,
    transaction_status: CreditTransactionStatus | None = None,
) -> WalletTotalCredits:
    async with pass_or_acquire_connection(engine, connection) as conn:
        sum_stmt = (
            sa.select(
                sa.func.SUM(resource_tracker_credit_transactions.c.osparc_credits),
            )
            .select_from(
                resource_tracker_service_runs.join(
                    resource_tracker_credit_transactions,
                    (
                        resource_tracker_service_runs.c.product_name
                        == resource_tracker_credit_transactions.c.product_name
                    )
                    & (
                        resource_tracker_service_runs.c.service_run_id
                        == resource_tracker_credit_transactions.c.service_run_id
                    ),
                    isouter=True,
                )
            )
            .where(
                (resource_tracker_service_runs.c.product_name == product_name)
                & (resource_tracker_service_runs.c.project_id == f"{project_id}")
                & (
                    resource_tracker_credit_transactions.c.transaction_classification
                    == CreditClassification.DEDUCT_SERVICE_RUN
                )
                & (resource_tracker_credit_transactions.c.wallet_id == wallet_id)
            )
        )

        if transaction_status:
            sum_stmt = sum_stmt.where(
                resource_tracker_credit_transactions.c.transaction_status
                == transaction_status
            )
        else:
            sum_stmt = sum_stmt.where(
                resource_tracker_credit_transactions.c.transaction_status.in_(
                    [
                        CreditTransactionStatus.BILLED,
                        CreditTransactionStatus.PENDING,
                        CreditTransactionStatus.IN_DEBT,
                    ]
                )
            )

        result = await conn.execute(sum_stmt)
        row = result.first()
        if row is None or row[0] is None:
            return WalletTotalCredits(
                wallet_id=wallet_id, available_osparc_credits=Decimal(0)
            )
        return WalletTotalCredits(wallet_id=wallet_id, available_osparc_credits=row[0])


async def export_service_runs_table_to_s3(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    s3_bucket_name: S3BucketName,
    s3_key: str,
    s3_region: str,
    user_id: UserID | None,
    wallet_id: WalletID | None,
    started_from: datetime | None = None,
    started_until: datetime | None = None,
    order_by: OrderBy | None = None,
):
    async with transaction_context(engine, connection) as conn:
        query = (
            sa.select(
                resource_tracker_service_runs.c.product_name,
                resource_tracker_service_runs.c.service_run_id,
                resource_tracker_service_runs.c.wallet_name,
                resource_tracker_service_runs.c.user_email,
                resource_tracker_service_runs.c.root_parent_project_name.label(
                    "project_name"
                ),
                resource_tracker_service_runs.c.node_name,
                resource_tracker_service_runs.c.service_key,
                resource_tracker_service_runs.c.service_version,
                resource_tracker_service_runs.c.service_type,
                resource_tracker_service_runs.c.started_at,
                resource_tracker_service_runs.c.stopped_at,
                resource_tracker_credit_transactions.c.osparc_credits,
                resource_tracker_credit_transactions.c.transaction_status,
                _project_tags_subquery.c.project_tags.label("project_tags"),
            )
            .select_from(
                resource_tracker_service_runs.join(
                    resource_tracker_credit_transactions,
                    resource_tracker_service_runs.c.service_run_id
                    == resource_tracker_credit_transactions.c.service_run_id,
                    isouter=True,
                ).join(
                    _project_tags_subquery,
                    resource_tracker_service_runs.c.project_id
                    == _project_tags_subquery.c.project_uuid_for_rut,
                    isouter=True,
                )
            )
            .where(resource_tracker_service_runs.c.product_name == product_name)
        )

        if user_id:
            query = query.where(resource_tracker_service_runs.c.user_id == user_id)
        if wallet_id:
            query = query.where(resource_tracker_service_runs.c.wallet_id == wallet_id)
        if started_from:
            query = query.where(
                sa.func.DATE(resource_tracker_service_runs.c.started_at)
                >= started_from.date()
            )
        if started_until:
            query = query.where(
                sa.func.DATE(resource_tracker_service_runs.c.started_at)
                <= started_until.date()
            )

        if order_by:
            if order_by.direction == OrderDirection.ASC:
                query = query.order_by(sa.asc(order_by.field))
            else:
                query = query.order_by(sa.desc(order_by.field))
        else:
            # Default ordering
            query = query.order_by(resource_tracker_service_runs.c.started_at.desc())

        compiled_query = (
            str(query.compile(compile_kwargs={"literal_binds": True}))
            .replace("\n", "")
            .replace("'", "''")
        )

        result = await conn.execute(
            sa.DDL(
                f"""
            SELECT * from aws_s3.query_export_to_s3('{compiled_query}',
            aws_commons.create_s3_uri('{s3_bucket_name}', '{s3_key}', '{s3_region}'), 'format csv, HEADER true');
            """  # noqa: S608
            )
        )
        row = result.first()
        assert row
        _logger.info(
            "Rows uploaded %s, Files uploaded %s, Bytes uploaded %s",
            row[0],
            row[1],
            row[2],
        )


async def total_service_runs_by_product_and_user_and_wallet(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    user_id: UserID | None,
    wallet_id: WalletID | None,
    service_run_status: ServiceRunStatus | None = None,
    started_from: datetime | None = None,
    started_until: datetime | None = None,
) -> PositiveInt:
    async with pass_or_acquire_connection(engine, connection) as conn:
        query = (
            sa.select(sa.func.count())
            .select_from(resource_tracker_service_runs)
            .where(resource_tracker_service_runs.c.product_name == product_name)
        )

        if user_id:
            query = query.where(resource_tracker_service_runs.c.user_id == user_id)
        if wallet_id:
            query = query.where(resource_tracker_service_runs.c.wallet_id == wallet_id)
        if started_from:
            query = query.where(
                sa.func.DATE(resource_tracker_service_runs.c.started_at)
                >= started_from.date()
            )
        if started_until:
            query = query.where(
                sa.func.DATE(resource_tracker_service_runs.c.started_at)
                <= started_until.date()
            )
        if service_run_status:
            query = query.where(
                resource_tracker_service_runs.c.service_run_status == service_run_status
            )

        result = await conn.execute(query)
    row = result.first()
    return cast(PositiveInt, row[0]) if row else 0


### For Background check purpose:


async def list_service_runs_with_running_status_across_all_products(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    offset: int,
    limit: int,
) -> list[ServiceRunForCheckDB]:
    async with pass_or_acquire_connection(engine, connection) as conn:
        query = (
            sa.select(
                resource_tracker_service_runs.c.service_run_id,
                resource_tracker_service_runs.c.last_heartbeat_at,
                resource_tracker_service_runs.c.missed_heartbeat_counter,
                resource_tracker_service_runs.c.modified,
            )
            .where(
                resource_tracker_service_runs.c.service_run_status
                == ServiceRunStatus.RUNNING
            )
            .order_by(resource_tracker_service_runs.c.started_at.desc())  # NOTE:
            .offset(offset)
            .limit(limit)
        )
        result = await conn.execute(query)

    return [ServiceRunForCheckDB.model_validate(row) for row in result.fetchall()]


async def total_service_runs_with_running_status_across_all_products(
    engine: AsyncEngine, connection: AsyncConnection | None = None
) -> PositiveInt:
    async with pass_or_acquire_connection(engine, connection) as conn:
        query = (
            sa.select(sa.func.count())
            .select_from(resource_tracker_service_runs)
            .where(
                resource_tracker_service_runs.c.service_run_status
                == ServiceRunStatus.RUNNING
            )
        )
        result = await conn.execute(query)
    row = result.first()
    return cast(PositiveInt, row[0]) if row else 0


async def update_service_missed_heartbeat_counter(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    service_run_id: ServiceRunID,
    last_heartbeat_at: datetime,
    missed_heartbeat_counter: int,
) -> ServiceRunDB | None:
    async with transaction_context(engine, connection) as conn:
        update_stmt = (
            resource_tracker_service_runs.update()
            .values(
                modified=sa.func.now(),
                missed_heartbeat_counter=missed_heartbeat_counter,
            )
            .where(
                (resource_tracker_service_runs.c.service_run_id == service_run_id)
                & (
                    resource_tracker_service_runs.c.service_run_status
                    == ServiceRunStatus.RUNNING
                )
                & (
                    resource_tracker_service_runs.c.last_heartbeat_at
                    == last_heartbeat_at
                )
            )
            .returning(sa.literal_column("*"))
        )

        result = await conn.execute(update_stmt)
    row = result.first()
    if row is None:
        return None
    return ServiceRunDB.model_validate(row)
