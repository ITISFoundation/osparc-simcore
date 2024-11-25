import logging
from datetime import datetime
from decimal import Decimal
from typing import cast

import sqlalchemy as sa
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    WalletTotalCredits,
)
from models_library.api_schemas_storage import S3BucketName
from models_library.products import ProductName
from models_library.resource_tracker import (
    CreditClassification,
    CreditTransactionId,
    CreditTransactionStatus,
    PricingPlanCreate,
    PricingPlanId,
    PricingPlanUpdate,
    PricingUnitCostId,
    PricingUnitId,
    PricingUnitWithCostCreate,
    PricingUnitWithCostUpdate,
    ServiceRunId,
    ServiceRunStatus,
)
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import PositiveInt
from simcore_postgres_database.models.projects_tags import projects_tags
from simcore_postgres_database.models.resource_tracker_credit_transactions import (
    resource_tracker_credit_transactions,
)
from simcore_postgres_database.models.resource_tracker_pricing_plan_to_service import (
    resource_tracker_pricing_plan_to_service,
)
from simcore_postgres_database.models.resource_tracker_pricing_plans import (
    resource_tracker_pricing_plans,
)
from simcore_postgres_database.models.resource_tracker_pricing_unit_costs import (
    resource_tracker_pricing_unit_costs,
)
from simcore_postgres_database.models.resource_tracker_pricing_units import (
    resource_tracker_pricing_units,
)
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
)
from simcore_postgres_database.models.tags import tags
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER

from .....exceptions.errors import (
    CreditTransactionNotCreatedDBError,
    PricingPlanAndPricingUnitCombinationDoesNotExistsDBError,
    PricingPlanDoesNotExistsDBError,
    PricingPlanNotCreatedDBError,
    PricingPlanToServiceNotCreatedDBError,
    PricingUnitCostDoesNotExistsDBError,
    PricingUnitCostNotCreatedDBError,
    PricingUnitNotCreatedDBError,
    ServiceRunNotCreatedDBError,
)
from .....models.credit_transactions import (
    CreditTransactionCreate,
    CreditTransactionCreditsAndStatusUpdate,
    CreditTransactionCreditsUpdate,
)
from .....models.pricing_plans import (
    PricingPlansDB,
    PricingPlansWithServiceDefaultPlanDB,
    PricingPlanToServiceDB,
)
from .....models.pricing_unit_costs import PricingUnitCostsDB
from .....models.pricing_units import PricingUnitsDB
from .....models.service_runs import (
    OsparcCreditsAggregatedByServiceKeyDB,
    ServiceRunCreate,
    ServiceRunDB,
    ServiceRunForCheckDB,
    ServiceRunLastHeartbeatUpdate,
    ServiceRunStoppedAtUpdate,
    ServiceRunWithCreditsDB,
)
from ._base import BaseRepository

_logger = logging.getLogger(__name__)


class ResourceTrackerRepository(
    BaseRepository
):  # pylint: disable=too-many-public-methods
    ###############
    # Service Run
    ###############

    async def create_service_run(self, data: ServiceRunCreate) -> ServiceRunId:
        async with self.db_engine.begin() as conn:
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
        return cast(ServiceRunId, row[0])

    async def update_service_run_last_heartbeat(
        self, data: ServiceRunLastHeartbeatUpdate
    ) -> ServiceRunDB | None:
        async with self.db_engine.begin() as conn:
            update_stmt = (
                resource_tracker_service_runs.update()
                .values(
                    modified=sa.func.now(),
                    last_heartbeat_at=data.last_heartbeat_at,
                    missed_heartbeat_counter=0,
                )
                .where(
                    (
                        resource_tracker_service_runs.c.service_run_id
                        == data.service_run_id
                    )
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
        self, data: ServiceRunStoppedAtUpdate
    ) -> ServiceRunDB | None:
        async with self.db_engine.begin() as conn:
            update_stmt = (
                resource_tracker_service_runs.update()
                .values(
                    modified=sa.func.now(),
                    stopped_at=data.stopped_at,
                    service_run_status=data.service_run_status,
                    service_run_status_msg=data.service_run_status_msg,
                )
                .where(
                    (
                        resource_tracker_service_runs.c.service_run_id
                        == data.service_run_id
                    )
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
        self, service_run_id: ServiceRunId
    ) -> ServiceRunDB | None:
        async with self.db_engine.begin() as conn:
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
        self,
        product_name: ProductName,
        *,
        user_id: UserID | None,
        wallet_id: WalletID | None,
        offset: int,
        limit: int,
        service_run_status: ServiceRunStatus | None = None,
        started_from: datetime | None = None,
        started_until: datetime | None = None,
        order_by: OrderBy | None = None,
    ) -> list[ServiceRunWithCreditsDB]:
        async with self.db_engine.begin() as conn:
            query = (
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
                        self._project_tags_subquery.c.project_tags,
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
                        self._project_tags_subquery,
                        resource_tracker_service_runs.c.project_id
                        == self._project_tags_subquery.c.project_uuid_for_rut,
                        isouter=True,
                    )
                )
                .where(resource_tracker_service_runs.c.product_name == product_name)
                .offset(offset)
                .limit(limit)
            )

            if user_id:
                query = query.where(resource_tracker_service_runs.c.user_id == user_id)
            if wallet_id:
                query = query.where(
                    resource_tracker_service_runs.c.wallet_id == wallet_id
                )
            if service_run_status:
                query = query.where(
                    resource_tracker_service_runs.c.service_run_status
                    == service_run_status
                )
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
                query = query.order_by(
                    resource_tracker_service_runs.c.started_at.desc()
                )

            result = await conn.execute(query)

        return [
            ServiceRunWithCreditsDB.model_validate(row) for row in result.fetchall()
        ]

    async def get_osparc_credits_aggregated_by_service(
        self,
        product_name: ProductName,
        *,
        user_id: UserID | None,
        wallet_id: WalletID,
        offset: int,
        limit: int,
        started_from: datetime | None = None,
        started_until: datetime | None = None,
    ) -> tuple[int, list[OsparcCreditsAggregatedByServiceKeyDB]]:
        async with self.db_engine.begin() as conn:
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
                        resource_tracker_credit_transactions.c.transaction_status
                        == CreditTransactionStatus.BILLED
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
            count_result = await conn.execute(count_query)

            # Default ordering and pagination
            list_query = (
                base_query.order_by(resource_tracker_service_runs.c.service_key.asc())
                .offset(offset)
                .limit(limit)
            )
            list_result = await conn.execute(list_query)

        return (
            cast(int, count_result.scalar()),
            [
                OsparcCreditsAggregatedByServiceKeyDB.model_validate(row)
                for row in list_result.fetchall()
            ],
        )

    async def export_service_runs_table_to_s3(
        self,
        product_name: ProductName,
        s3_bucket_name: S3BucketName,
        s3_key: str,
        s3_region: str,
        *,
        user_id: UserID | None,
        wallet_id: WalletID | None,
        started_from: datetime | None = None,
        started_until: datetime | None = None,
        order_by: OrderBy | None = None,
    ):
        async with self.db_engine.begin() as conn:
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
                    sa.func.coalesce(
                        self._project_tags_subquery.c.project_tags,
                        sa.cast(sa.text("'{}'"), sa.ARRAY(sa.String)),
                    ).label("project_tags"),
                )
                .select_from(
                    resource_tracker_service_runs.join(
                        resource_tracker_credit_transactions,
                        resource_tracker_service_runs.c.service_run_id
                        == resource_tracker_credit_transactions.c.service_run_id,
                        isouter=True,
                    ).join(
                        self._project_tags_subquery,
                        resource_tracker_service_runs.c.project_id
                        == self._project_tags_subquery.c.project_uuid_for_rut,
                        isouter=True,
                    )
                )
                .where(resource_tracker_service_runs.c.product_name == product_name)
            )

            if user_id:
                query = query.where(resource_tracker_service_runs.c.user_id == user_id)
            if wallet_id:
                query = query.where(
                    resource_tracker_service_runs.c.wallet_id == wallet_id
                )
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
                query = query.order_by(
                    resource_tracker_service_runs.c.started_at.desc()
                )

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
        self,
        product_name: ProductName,
        *,
        user_id: UserID | None,
        wallet_id: WalletID | None,
        service_run_status: ServiceRunStatus | None = None,
        started_from: datetime | None = None,
        started_until: datetime | None = None,
    ) -> PositiveInt:
        async with self.db_engine.begin() as conn:
            query = (
                sa.select(sa.func.count())
                .select_from(resource_tracker_service_runs)
                .where(resource_tracker_service_runs.c.product_name == product_name)
            )

            if user_id:
                query = query.where(resource_tracker_service_runs.c.user_id == user_id)
            if wallet_id:
                query = query.where(
                    resource_tracker_service_runs.c.wallet_id == wallet_id
                )
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
                    resource_tracker_service_runs.c.service_run_status
                    == service_run_status
                )

            result = await conn.execute(query)
        row = result.first()
        return cast(PositiveInt, row[0]) if row else 0

    ### For Background check purpose:

    async def list_service_runs_with_running_status_across_all_products(
        self,
        *,
        offset: int,
        limit: int,
    ) -> list[ServiceRunForCheckDB]:
        async with self.db_engine.begin() as conn:
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
        self,
    ) -> PositiveInt:
        async with self.db_engine.begin() as conn:
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
        self,
        service_run_id: ServiceRunId,
        last_heartbeat_at: datetime,
        missed_heartbeat_counter: int,
    ) -> ServiceRunDB | None:
        async with self.db_engine.begin() as conn:
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

    #################################
    # Credit transactions
    #################################

    async def create_credit_transaction(
        self, data: CreditTransactionCreate
    ) -> CreditTransactionId:
        async with self.db_engine.begin() as conn:
            insert_stmt = (
                resource_tracker_credit_transactions.insert()
                .values(
                    product_name=data.product_name,
                    wallet_id=data.wallet_id,
                    wallet_name=data.wallet_name,
                    pricing_plan_id=data.pricing_plan_id,
                    pricing_unit_id=data.pricing_unit_id,
                    pricing_unit_cost_id=data.pricing_unit_cost_id,
                    user_id=data.user_id,
                    user_email=data.user_email,
                    osparc_credits=data.osparc_credits,
                    transaction_status=data.transaction_status,
                    transaction_classification=data.transaction_classification,
                    service_run_id=data.service_run_id,
                    payment_transaction_id=data.payment_transaction_id,
                    created=data.created_at,
                    last_heartbeat_at=data.last_heartbeat_at,
                    modified=sa.func.now(),
                )
                .returning(resource_tracker_credit_transactions.c.transaction_id)
            )
            result = await conn.execute(insert_stmt)
        row = result.first()
        if row is None:
            raise CreditTransactionNotCreatedDBError(data=data)
        return cast(CreditTransactionId, row[0])

    async def update_credit_transaction_credits(
        self, data: CreditTransactionCreditsUpdate
    ) -> CreditTransactionId | None:
        async with self.db_engine.begin() as conn:
            update_stmt = (
                resource_tracker_credit_transactions.update()
                .values(
                    modified=sa.func.now(),
                    osparc_credits=data.osparc_credits,
                    last_heartbeat_at=data.last_heartbeat_at,
                )
                .where(
                    (
                        resource_tracker_credit_transactions.c.service_run_id
                        == data.service_run_id
                    )
                    & (
                        resource_tracker_credit_transactions.c.transaction_status
                        == CreditTransactionStatus.PENDING
                    )
                    & (
                        resource_tracker_credit_transactions.c.last_heartbeat_at
                        <= data.last_heartbeat_at
                    )
                )
                .returning(resource_tracker_credit_transactions.c.service_run_id)
            )
            result = await conn.execute(update_stmt)
        row = result.first()
        if row is None:
            return None
        return cast(CreditTransactionId | None, row[0])

    async def update_credit_transaction_credits_and_status(
        self, data: CreditTransactionCreditsAndStatusUpdate
    ) -> CreditTransactionId | None:
        async with self.db_engine.begin() as conn:
            update_stmt = (
                resource_tracker_credit_transactions.update()
                .values(
                    modified=sa.func.now(),
                    osparc_credits=data.osparc_credits,
                    transaction_status=data.transaction_status,
                )
                .where(
                    (
                        resource_tracker_credit_transactions.c.service_run_id
                        == data.service_run_id
                    )
                    & (
                        resource_tracker_credit_transactions.c.transaction_status
                        == CreditTransactionStatus.PENDING
                    )
                )
                .returning(resource_tracker_credit_transactions.c.service_run_id)
            )
            result = await conn.execute(update_stmt)
        row = result.first()
        if row is None:
            return None
        return cast(CreditTransactionId | None, row[0])

    async def sum_credit_transactions_by_product_and_wallet(
        self, product_name: ProductName, wallet_id: WalletID
    ) -> WalletTotalCredits:
        async with self.db_engine.begin() as conn:
            sum_stmt = sa.select(
                sa.func.sum(resource_tracker_credit_transactions.c.osparc_credits)
            ).where(
                (resource_tracker_credit_transactions.c.product_name == product_name)
                & (resource_tracker_credit_transactions.c.wallet_id == wallet_id)
                & (
                    resource_tracker_credit_transactions.c.transaction_status.in_(
                        [
                            CreditTransactionStatus.BILLED,
                            CreditTransactionStatus.PENDING,
                        ]
                    )
                )
            )
            result = await conn.execute(sum_stmt)
        row = result.first()
        if row is None or row[0] is None:
            return WalletTotalCredits(
                wallet_id=wallet_id, available_osparc_credits=Decimal(0)
            )
        return WalletTotalCredits(wallet_id=wallet_id, available_osparc_credits=row[0])

    #################################
    # Pricing plans
    #################################

    async def list_active_service_pricing_plans_by_product_and_service(
        self,
        product_name: ProductName,
        service_key: ServiceKey,
        service_version: ServiceVersion,
    ) -> list[PricingPlansWithServiceDefaultPlanDB]:
        # NOTE: consilidate with utils_services_environmnets.py
        def _version(column_or_value):
            # converts version value string to array[integer] that can be compared
            return sa.func.string_to_array(column_or_value, ".").cast(ARRAY(INTEGER))

        async with self.db_engine.begin() as conn:
            # Firstly find the correct service version
            query = (
                sa.select(
                    resource_tracker_pricing_plan_to_service.c.service_key,
                    resource_tracker_pricing_plan_to_service.c.service_version,
                )
                .select_from(
                    resource_tracker_pricing_plan_to_service.join(
                        resource_tracker_pricing_plans,
                        (
                            resource_tracker_pricing_plan_to_service.c.pricing_plan_id
                            == resource_tracker_pricing_plans.c.pricing_plan_id
                        ),
                    )
                )
                .where(
                    (
                        _version(
                            resource_tracker_pricing_plan_to_service.c.service_version
                        )
                        <= _version(service_version)
                    )
                    & (
                        resource_tracker_pricing_plan_to_service.c.service_key
                        == service_key
                    )
                    & (resource_tracker_pricing_plans.c.product_name == product_name)
                    & (resource_tracker_pricing_plans.c.is_active.is_(True))
                )
                .order_by(
                    _version(
                        resource_tracker_pricing_plan_to_service.c.service_version
                    ).desc()
                )
                .limit(1)
            )
            result = await conn.execute(query)
            row = result.first()
            if row is None:
                return []
            latest_service_key, latest_service_version = row
            # Now choose all pricing plans connected to this service
            query = (
                sa.select(
                    resource_tracker_pricing_plans.c.pricing_plan_id,
                    resource_tracker_pricing_plans.c.display_name,
                    resource_tracker_pricing_plans.c.description,
                    resource_tracker_pricing_plans.c.classification,
                    resource_tracker_pricing_plans.c.is_active,
                    resource_tracker_pricing_plans.c.created,
                    resource_tracker_pricing_plans.c.pricing_plan_key,
                    resource_tracker_pricing_plan_to_service.c.service_default_plan,
                )
                .select_from(
                    resource_tracker_pricing_plan_to_service.join(
                        resource_tracker_pricing_plans,
                        (
                            resource_tracker_pricing_plan_to_service.c.pricing_plan_id
                            == resource_tracker_pricing_plans.c.pricing_plan_id
                        ),
                    )
                )
                .where(
                    (
                        _version(
                            resource_tracker_pricing_plan_to_service.c.service_version
                        )
                        == _version(latest_service_version)
                    )
                    & (
                        resource_tracker_pricing_plan_to_service.c.service_key
                        == latest_service_key
                    )
                    & (resource_tracker_pricing_plans.c.product_name == product_name)
                    & (resource_tracker_pricing_plans.c.is_active.is_(True))
                )
                .order_by(
                    resource_tracker_pricing_plan_to_service.c.pricing_plan_id.desc()
                )
            )
            result = await conn.execute(query)

        return [
            PricingPlansWithServiceDefaultPlanDB.model_validate(row)
            for row in result.fetchall()
        ]

    async def get_pricing_plan(
        self, product_name: ProductName, pricing_plan_id: PricingPlanId
    ) -> PricingPlansDB:
        async with self.db_engine.begin() as conn:
            select_stmt = sa.select(
                resource_tracker_pricing_plans.c.pricing_plan_id,
                resource_tracker_pricing_plans.c.display_name,
                resource_tracker_pricing_plans.c.description,
                resource_tracker_pricing_plans.c.classification,
                resource_tracker_pricing_plans.c.is_active,
                resource_tracker_pricing_plans.c.created,
                resource_tracker_pricing_plans.c.pricing_plan_key,
            ).where(
                (resource_tracker_pricing_plans.c.pricing_plan_id == pricing_plan_id)
                & (resource_tracker_pricing_plans.c.product_name == product_name)
            )
            result = await conn.execute(select_stmt)
        row = result.first()
        if row is None:
            raise PricingPlanDoesNotExistsDBError(pricing_plan_id=pricing_plan_id)
        return PricingPlansDB.model_validate(row)

    async def list_pricing_plans_by_product(
        self, product_name: ProductName
    ) -> list[PricingPlansDB]:
        async with self.db_engine.begin() as conn:
            select_stmt = sa.select(
                resource_tracker_pricing_plans.c.pricing_plan_id,
                resource_tracker_pricing_plans.c.display_name,
                resource_tracker_pricing_plans.c.description,
                resource_tracker_pricing_plans.c.classification,
                resource_tracker_pricing_plans.c.is_active,
                resource_tracker_pricing_plans.c.created,
                resource_tracker_pricing_plans.c.pricing_plan_key,
            ).where(resource_tracker_pricing_plans.c.product_name == product_name)
            result = await conn.execute(select_stmt)

        return [PricingPlansDB.model_validate(row) for row in result.fetchall()]

    async def create_pricing_plan(self, data: PricingPlanCreate) -> PricingPlansDB:
        async with self.db_engine.begin() as conn:
            insert_stmt = (
                resource_tracker_pricing_plans.insert()
                .values(
                    product_name=data.product_name,
                    display_name=data.display_name,
                    description=data.description,
                    classification=data.classification,
                    is_active=True,
                    created=sa.func.now(),
                    modified=sa.func.now(),
                    pricing_plan_key=data.pricing_plan_key,
                )
                .returning(
                    *[
                        resource_tracker_pricing_plans.c.pricing_plan_id,
                        resource_tracker_pricing_plans.c.display_name,
                        resource_tracker_pricing_plans.c.description,
                        resource_tracker_pricing_plans.c.classification,
                        resource_tracker_pricing_plans.c.is_active,
                        resource_tracker_pricing_plans.c.created,
                        resource_tracker_pricing_plans.c.pricing_plan_key,
                    ]
                )
            )
            result = await conn.execute(insert_stmt)
        row = result.first()
        if row is None:
            raise PricingPlanNotCreatedDBError(data=data)
        return PricingPlansDB.model_validate(row)

    async def update_pricing_plan(
        self, product_name: ProductName, data: PricingPlanUpdate
    ) -> PricingPlansDB | None:
        async with self.db_engine.begin() as conn:
            update_stmt = (
                resource_tracker_pricing_plans.update()
                .values(
                    display_name=data.display_name,
                    description=data.description,
                    is_active=data.is_active,
                    modified=sa.func.now(),
                )
                .where(
                    (
                        resource_tracker_pricing_plans.c.pricing_plan_id
                        == data.pricing_plan_id
                    )
                    & (resource_tracker_pricing_plans.c.product_name == product_name)
                )
                .returning(
                    *[
                        resource_tracker_pricing_plans.c.pricing_plan_id,
                        resource_tracker_pricing_plans.c.display_name,
                        resource_tracker_pricing_plans.c.description,
                        resource_tracker_pricing_plans.c.classification,
                        resource_tracker_pricing_plans.c.is_active,
                        resource_tracker_pricing_plans.c.created,
                        resource_tracker_pricing_plans.c.pricing_plan_key,
                    ]
                )
            )
            result = await conn.execute(update_stmt)
        row = result.first()
        if row is None:
            return None
        return PricingPlansDB.model_validate(row)

    #################################
    # Pricing plan to service
    #################################

    async def list_connected_services_to_pricing_plan_by_pricing_plan(
        self, product_name: ProductName, pricing_plan_id: PricingPlanId
    ) -> list[PricingPlanToServiceDB]:
        async with self.db_engine.begin() as conn:
            query = (
                sa.select(
                    resource_tracker_pricing_plan_to_service.c.pricing_plan_id,
                    resource_tracker_pricing_plan_to_service.c.service_key,
                    resource_tracker_pricing_plan_to_service.c.service_version,
                    resource_tracker_pricing_plan_to_service.c.created,
                )
                .select_from(
                    resource_tracker_pricing_plan_to_service.join(
                        resource_tracker_pricing_plans,
                        (
                            resource_tracker_pricing_plan_to_service.c.pricing_plan_id
                            == resource_tracker_pricing_plans.c.pricing_plan_id
                        ),
                    )
                )
                .where(
                    (resource_tracker_pricing_plans.c.product_name == product_name)
                    & (
                        resource_tracker_pricing_plans.c.pricing_plan_id
                        == pricing_plan_id
                    )
                )
                .order_by(
                    resource_tracker_pricing_plan_to_service.c.pricing_plan_id.desc()
                )
            )
            result = await conn.execute(query)

            return [
                PricingPlanToServiceDB.model_validate(row) for row in result.fetchall()
            ]

    async def upsert_service_to_pricing_plan(
        self,
        product_name: ProductName,
        pricing_plan_id: PricingPlanId,
        service_key: ServiceKey,
        service_version: ServiceVersion,
    ) -> PricingPlanToServiceDB:
        async with self.db_engine.begin() as conn:
            query = (
                sa.select(
                    resource_tracker_pricing_plan_to_service.c.pricing_plan_id,
                    resource_tracker_pricing_plan_to_service.c.service_key,
                    resource_tracker_pricing_plan_to_service.c.service_version,
                    resource_tracker_pricing_plan_to_service.c.created,
                )
                .select_from(
                    resource_tracker_pricing_plan_to_service.join(
                        resource_tracker_pricing_plans,
                        (
                            resource_tracker_pricing_plan_to_service.c.pricing_plan_id
                            == resource_tracker_pricing_plans.c.pricing_plan_id
                        ),
                    )
                )
                .where(
                    (resource_tracker_pricing_plans.c.product_name == product_name)
                    & (
                        resource_tracker_pricing_plans.c.pricing_plan_id
                        == pricing_plan_id
                    )
                    & (
                        resource_tracker_pricing_plan_to_service.c.service_key
                        == service_key
                    )
                    & (
                        resource_tracker_pricing_plan_to_service.c.service_version
                        == service_version
                    )
                )
            )
            result = await conn.execute(query)
            row = result.first()

            if row is not None:
                delete_stmt = resource_tracker_pricing_plan_to_service.delete().where(
                    (
                        resource_tracker_pricing_plans.c.pricing_plan_id
                        == pricing_plan_id
                    )
                    & (
                        resource_tracker_pricing_plan_to_service.c.service_key
                        == service_key
                    )
                    & (
                        resource_tracker_pricing_plan_to_service.c.service_version
                        == service_version
                    )
                )
                await conn.execute(delete_stmt)

            insert_stmt = (
                resource_tracker_pricing_plan_to_service.insert()
                .values(
                    pricing_plan_id=pricing_plan_id,
                    service_key=service_key,
                    service_version=service_version,
                    created=sa.func.now(),
                    modified=sa.func.now(),
                    service_default_plan=True,
                )
                .returning(
                    *[
                        resource_tracker_pricing_plan_to_service.c.pricing_plan_id,
                        resource_tracker_pricing_plan_to_service.c.service_key,
                        resource_tracker_pricing_plan_to_service.c.service_version,
                        resource_tracker_pricing_plan_to_service.c.created,
                    ]
                )
            )
            result = await conn.execute(insert_stmt)
            row = result.first()
            if row is None:
                raise PricingPlanToServiceNotCreatedDBError(
                    data=f"pricing_plan_id {pricing_plan_id}, service_key {service_key}, service_version {service_version}"
                )
            return PricingPlanToServiceDB.model_validate(row)

    #################################
    # Pricing units
    #################################

    @staticmethod
    def _pricing_units_select_stmt():
        return sa.select(
            resource_tracker_pricing_units.c.pricing_unit_id,
            resource_tracker_pricing_units.c.pricing_plan_id,
            resource_tracker_pricing_units.c.unit_name,
            resource_tracker_pricing_units.c.unit_extra_info,
            resource_tracker_pricing_units.c.default,
            resource_tracker_pricing_units.c.specific_info,
            resource_tracker_pricing_units.c.created,
            resource_tracker_pricing_units.c.modified,
            resource_tracker_pricing_unit_costs.c.cost_per_unit.label(
                "current_cost_per_unit"
            ),
            resource_tracker_pricing_unit_costs.c.pricing_unit_cost_id.label(
                "current_cost_per_unit_id"
            ),
        )

    async def list_pricing_units_by_pricing_plan(
        self,
        pricing_plan_id: PricingPlanId,
    ) -> list[PricingUnitsDB]:
        async with self.db_engine.begin() as conn:
            query = (
                self._pricing_units_select_stmt()
                .select_from(
                    resource_tracker_pricing_units.join(
                        resource_tracker_pricing_unit_costs,
                        (
                            (
                                resource_tracker_pricing_units.c.pricing_plan_id
                                == resource_tracker_pricing_unit_costs.c.pricing_plan_id
                            )
                            & (
                                resource_tracker_pricing_units.c.pricing_unit_id
                                == resource_tracker_pricing_unit_costs.c.pricing_unit_id
                            )
                        ),
                    )
                )
                .where(
                    (
                        resource_tracker_pricing_units.c.pricing_plan_id
                        == pricing_plan_id
                    )
                    & (resource_tracker_pricing_unit_costs.c.valid_to.is_(None))
                )
                .order_by(resource_tracker_pricing_unit_costs.c.cost_per_unit.asc())
            )
            result = await conn.execute(query)

        return [PricingUnitsDB.model_validate(row) for row in result.fetchall()]

    async def get_valid_pricing_unit(
        self,
        product_name: ProductName,
        pricing_plan_id: PricingPlanId,
        pricing_unit_id: PricingUnitId,
    ) -> PricingUnitsDB:
        async with self.db_engine.begin() as conn:
            query = (
                self._pricing_units_select_stmt()
                .select_from(
                    resource_tracker_pricing_units.join(
                        resource_tracker_pricing_unit_costs,
                        (
                            (
                                resource_tracker_pricing_units.c.pricing_plan_id
                                == resource_tracker_pricing_unit_costs.c.pricing_plan_id
                            )
                            & (
                                resource_tracker_pricing_units.c.pricing_unit_id
                                == resource_tracker_pricing_unit_costs.c.pricing_unit_id
                            )
                        ),
                    ).join(
                        resource_tracker_pricing_plans,
                        (
                            resource_tracker_pricing_plans.c.pricing_plan_id
                            == resource_tracker_pricing_units.c.pricing_plan_id
                        ),
                    )
                )
                .where(
                    (
                        resource_tracker_pricing_units.c.pricing_plan_id
                        == pricing_plan_id
                    )
                    & (
                        resource_tracker_pricing_units.c.pricing_unit_id
                        == pricing_unit_id
                    )
                    & (resource_tracker_pricing_unit_costs.c.valid_to.is_(None))
                    & (resource_tracker_pricing_plans.c.product_name == product_name)
                )
            )
            result = await conn.execute(query)

        row = result.first()
        if row is None:
            raise PricingPlanAndPricingUnitCombinationDoesNotExistsDBError(
                pricing_plan_id=pricing_plan_id,
                pricing_unit_id=pricing_unit_id,
                product_name=product_name,
            )
        return PricingUnitsDB.model_validate(row)

    async def create_pricing_unit_with_cost(
        self, data: PricingUnitWithCostCreate, pricing_plan_key: str
    ) -> tuple[PricingUnitId, PricingUnitCostId]:
        async with self.db_engine.begin() as conn:
            # pricing units table
            insert_stmt = (
                resource_tracker_pricing_units.insert()
                .values(
                    pricing_plan_id=data.pricing_plan_id,
                    unit_name=data.unit_name,
                    unit_extra_info=data.unit_extra_info.model_dump(),
                    default=data.default,
                    specific_info=data.specific_info.model_dump(),
                    created=sa.func.now(),
                    modified=sa.func.now(),
                )
                .returning(resource_tracker_pricing_units.c.pricing_unit_id)
            )
            result = await conn.execute(insert_stmt)
            row = result.first()
            if row is None:
                raise PricingUnitNotCreatedDBError(data=data)
            _pricing_unit_id = row[0]

            # pricing unit cost table
            insert_stmt = (
                resource_tracker_pricing_unit_costs.insert()
                .values(
                    pricing_plan_id=data.pricing_plan_id,
                    pricing_plan_key=pricing_plan_key,
                    pricing_unit_id=_pricing_unit_id,
                    pricing_unit_name=data.unit_name,
                    cost_per_unit=data.cost_per_unit,
                    valid_from=sa.func.now(),
                    valid_to=None,
                    created=sa.func.now(),
                    comment=data.comment,
                    modified=sa.func.now(),
                )
                .returning(resource_tracker_pricing_unit_costs.c.pricing_unit_cost_id)
            )
            result = await conn.execute(insert_stmt)
            row = result.first()
            if row is None:
                raise PricingUnitCostNotCreatedDBError(data=data)
            _pricing_unit_cost_id = row[0]

        return (_pricing_unit_id, _pricing_unit_cost_id)

    async def update_pricing_unit_with_cost(
        self, data: PricingUnitWithCostUpdate, pricing_plan_key: str
    ) -> None:
        async with self.db_engine.begin() as conn:
            # pricing units table
            update_stmt = (
                resource_tracker_pricing_units.update()
                .values(
                    unit_name=data.unit_name,
                    unit_extra_info=data.unit_extra_info.model_dump(),
                    default=data.default,
                    specific_info=data.specific_info.model_dump(),
                    modified=sa.func.now(),
                )
                .where(
                    resource_tracker_pricing_units.c.pricing_unit_id
                    == data.pricing_unit_id
                )
                .returning(resource_tracker_pricing_units.c.pricing_unit_id)
            )
            await conn.execute(update_stmt)

            # If price change, then we update pricing unit cost table
            if data.pricing_unit_cost_update:
                # Firstly we close previous price
                update_stmt = (
                    resource_tracker_pricing_unit_costs.update()
                    .values(
                        valid_to=sa.func.now(),  # <-- Closing previous price
                        modified=sa.func.now(),
                    )
                    .where(
                        resource_tracker_pricing_unit_costs.c.pricing_unit_id
                        == data.pricing_unit_id
                    )
                    .returning(resource_tracker_pricing_unit_costs.c.pricing_unit_id)
                )
                result = await conn.execute(update_stmt)

                # Then we create a new price
                insert_stmt = (
                    resource_tracker_pricing_unit_costs.insert()
                    .values(
                        pricing_plan_id=data.pricing_plan_id,
                        pricing_plan_key=pricing_plan_key,
                        pricing_unit_id=data.pricing_unit_id,
                        pricing_unit_name=data.unit_name,
                        cost_per_unit=data.pricing_unit_cost_update.cost_per_unit,
                        valid_from=sa.func.now(),
                        valid_to=None,  # <-- New price is valid
                        created=sa.func.now(),
                        comment=data.pricing_unit_cost_update.comment,
                        modified=sa.func.now(),
                    )
                    .returning(
                        resource_tracker_pricing_unit_costs.c.pricing_unit_cost_id
                    )
                )
                result = await conn.execute(insert_stmt)
                row = result.first()
                if row is None:
                    raise PricingUnitCostNotCreatedDBError(data=data)

    #################################
    # Pricing unit-costs
    #################################

    async def get_pricing_unit_cost_by_id(
        self, pricing_unit_cost_id: PricingUnitCostId
    ) -> PricingUnitCostsDB:
        async with self.db_engine.begin() as conn:
            query = sa.select(
                resource_tracker_pricing_unit_costs.c.pricing_unit_cost_id,
                resource_tracker_pricing_unit_costs.c.pricing_plan_id,
                resource_tracker_pricing_unit_costs.c.pricing_plan_key,
                resource_tracker_pricing_unit_costs.c.pricing_unit_id,
                resource_tracker_pricing_unit_costs.c.pricing_unit_name,
                resource_tracker_pricing_unit_costs.c.cost_per_unit,
                resource_tracker_pricing_unit_costs.c.valid_from,
                resource_tracker_pricing_unit_costs.c.valid_to,
                resource_tracker_pricing_unit_costs.c.created,
                resource_tracker_pricing_unit_costs.c.comment,
                resource_tracker_pricing_unit_costs.c.modified,
            ).where(
                resource_tracker_pricing_unit_costs.c.pricing_unit_cost_id
                == pricing_unit_cost_id
            )
            result = await conn.execute(query)

        row = result.first()
        if row is None:
            raise PricingUnitCostDoesNotExistsDBError(
                pricing_unit_cost_id=pricing_unit_cost_id
            )
        return PricingUnitCostsDB.model_validate(row)
