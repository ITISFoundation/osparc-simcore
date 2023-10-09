import logging
from decimal import Decimal
from typing import cast

import sqlalchemy as sa
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    WalletTotalCredits,
)
from models_library.products import ProductName
from models_library.resource_tracker import (
    CreditTransactionId,
    CreditTransactionStatus,
    PricingPlanId,
    PricingUnitCostId,
    PricingUnitId,
    ServiceRunId,
    ServiceRunStatus,
)
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import PositiveInt
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
from simcore_service_resource_usage_tracker.models.resource_tracker_pricing_unit_costs import (
    PricingUnitCostsDB,
)
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER

from ....core.errors import CustomResourceUsageTrackerRuntimeError
from ....models.resource_tracker_credit_transactions import (
    CreditTransactionCreate,
    CreditTransactionCreditsAndStatusUpdate,
    CreditTransactionCreditsUpdate,
)
from ....models.resource_tracker_pricing_plans import (
    PricingPlansWithServiceDefaultPlanDB,
)
from ....models.resource_tracker_pricing_units import PricingUnitsDB
from ....models.resource_tracker_service_runs import (
    ServiceRunCreate,
    ServiceRunDB,
    ServiceRunLastHeartbeatUpdate,
    ServiceRunStoppedAtUpdate,
    ServiceRunWithCreditsDB,
)
from ._base import BaseRepository

_logger = logging.getLogger(__name__)


class ResourceTrackerRepository(BaseRepository):
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
                    project_name=data.product_name,
                    node_id=f"{data.node_id}",
                    node_name=data.node_name,
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
            raise CustomResourceUsageTrackerRuntimeError(
                msg=f"Service was not created: {data}"
            )
        return row[0]

    async def update_service_run_last_heartbeat(
        self, data: ServiceRunLastHeartbeatUpdate
    ) -> ServiceRunDB | None:
        async with self.db_engine.begin() as conn:
            update_stmt = (
                resource_tracker_service_runs.update()
                .values(
                    modified=sa.func.now(), last_heartbeat_at=data.last_heartbeat_at
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
        return ServiceRunDB.from_orm(row)

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
        return ServiceRunDB.from_orm(row)

    async def list_service_runs_by_product_and_user_and_wallet(
        self,
        product_name: ProductName,
        user_id: UserID | None,
        wallet_id: WalletID | None,
        offset: int,
        limit: int,
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
                    resource_tracker_service_runs.c.service_key,
                    resource_tracker_service_runs.c.service_version,
                    resource_tracker_service_runs.c.service_type,
                    resource_tracker_service_runs.c.service_resources,
                    resource_tracker_service_runs.c.started_at,
                    resource_tracker_service_runs.c.stopped_at,
                    resource_tracker_service_runs.c.service_run_status,
                    resource_tracker_service_runs.c.modified,
                    resource_tracker_service_runs.c.last_heartbeat_at,
                    resource_tracker_credit_transactions.c.osparc_credits,
                    resource_tracker_credit_transactions.c.transaction_status,
                )
                .select_from(
                    resource_tracker_service_runs.join(
                        resource_tracker_credit_transactions,
                        resource_tracker_service_runs.c.service_run_id
                        == resource_tracker_credit_transactions.c.service_run_id,
                        isouter=True,
                    )
                )
                .where(resource_tracker_service_runs.c.product_name == product_name)
                .order_by(resource_tracker_service_runs.c.started_at.desc())
                .offset(offset)
                .limit(limit)
            )

            if user_id:
                query = query.where(resource_tracker_service_runs.c.user_id == user_id)
            if wallet_id:
                query = query.where(
                    resource_tracker_service_runs.c.wallet_id == wallet_id
                )

            result = await conn.execute(query)

        return [ServiceRunWithCreditsDB.from_orm(row) for row in result.fetchall()]

    async def total_service_runs_by_product_and_user_and_wallet(
        self,
        product_name: ProductName,
        user_id: UserID | None,
        wallet_id: WalletID | None,
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

            result = await conn.execute(query)
        row = result.first()
        return cast(PositiveInt, row[0]) if row else 0

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
            raise CustomResourceUsageTrackerRuntimeError(
                msg=f"Transaction was not created: {data}"
            )
        return row[0]

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
        return row[0]

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
        return row[0]

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
            PricingPlansWithServiceDefaultPlanDB.from_orm(row)
            for row in result.fetchall()
        ]

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

        return [PricingUnitsDB.from_orm(row) for row in result.fetchall()]

    async def get_pricing_unit(
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
            raise CustomResourceUsageTrackerRuntimeError(
                msg=f"Pricing unit id {pricing_unit_id} not found"
            )
        return PricingUnitsDB.from_orm(row)

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
            raise CustomResourceUsageTrackerRuntimeError(
                msg=f"Pricing unit cosd id {pricing_unit_cost_id} not found in the resource_tracker_pricing_unit_costs table",
            )
        return PricingUnitCostsDB.from_orm(row)
