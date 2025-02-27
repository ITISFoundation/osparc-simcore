import logging
from typing import cast

import sqlalchemy as sa
from models_library.products import ProductName
from models_library.resource_tracker import (
    PricingPlanCreate,
    PricingPlanId,
    PricingPlanUpdate,
    PricingUnitCostId,
    PricingUnitId,
    PricingUnitWithCostCreate,
    PricingUnitWithCostUpdate,
)
from models_library.services import ServiceKey, ServiceVersion
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    PricingUnitDuplicationError,
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
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER
from sqlalchemy.exc import IntegrityError as SqlAlchemyIntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ....exceptions.errors import (
    PricingPlanAndPricingUnitCombinationDoesNotExistsDBError,
    PricingPlanDoesNotExistsDBError,
    PricingPlanNotCreatedDBError,
    PricingPlanToServiceNotCreatedDBError,
    PricingUnitCostDoesNotExistsDBError,
    PricingUnitCostNotCreatedDBError,
    PricingUnitNotCreatedDBError,
)
from ....models.pricing_plans import (
    PricingPlansDB,
    PricingPlansWithServiceDefaultPlanDB,
    PricingPlanToServiceDB,
)
from ....models.pricing_unit_costs import PricingUnitCostsDB
from ....models.pricing_units import PricingUnitsDB

_logger = logging.getLogger(__name__)


#################################
# Pricing plans
#################################


async def list_active_service_pricing_plans_by_product_and_service(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> list[PricingPlansWithServiceDefaultPlanDB]:
    # NOTE: consilidate with utils_services_environmnets.py
    def _version(column_or_value):
        # converts version value string to array[integer] that can be compared
        return sa.func.string_to_array(column_or_value, ".").cast(ARRAY(INTEGER))

    async with transaction_context(engine, connection) as conn:
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
                    _version(resource_tracker_pricing_plan_to_service.c.service_version)
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
                    _version(resource_tracker_pricing_plan_to_service.c.service_version)
                    == _version(latest_service_version)
                )
                & (
                    resource_tracker_pricing_plan_to_service.c.service_key
                    == latest_service_key
                )
                & (resource_tracker_pricing_plans.c.product_name == product_name)
                & (resource_tracker_pricing_plans.c.is_active.is_(True))
            )
            .order_by(resource_tracker_pricing_plan_to_service.c.pricing_plan_id.desc())
        )
        result = await conn.execute(query)

    return [
        PricingPlansWithServiceDefaultPlanDB.model_validate(row)
        for row in result.fetchall()
    ]


async def get_pricing_plan(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
) -> PricingPlansDB:
    async with transaction_context(engine, connection) as conn:
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
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    exclude_inactive: bool,
    # pagination
    offset: int,
    limit: int,
) -> tuple[int, list[PricingPlansDB]]:
    async with transaction_context(engine, connection) as conn:
        base_query = sa.select(
            resource_tracker_pricing_plans.c.pricing_plan_id,
            resource_tracker_pricing_plans.c.display_name,
            resource_tracker_pricing_plans.c.description,
            resource_tracker_pricing_plans.c.classification,
            resource_tracker_pricing_plans.c.is_active,
            resource_tracker_pricing_plans.c.created,
            resource_tracker_pricing_plans.c.pricing_plan_key,
        ).where(resource_tracker_pricing_plans.c.product_name == product_name)

        if exclude_inactive is True:
            base_query = base_query.where(
                resource_tracker_pricing_plans.c.is_active.is_(True)
            )

        # Select total count from base_query
        subquery = base_query.subquery()
        count_query = sa.select(sa.func.count()).select_from(subquery)

        # Default ordering
        list_query = base_query.order_by(
            resource_tracker_pricing_plans.c.created.asc(),
            resource_tracker_pricing_plans.c.pricing_plan_id,
        )

        total_count = await conn.scalar(count_query)
        if total_count is None:
            total_count = 0

        result = await conn.execute(list_query.offset(offset).limit(limit))

    items = [PricingPlansDB.model_validate(row) for row in result.fetchall()]
    return cast(int, total_count), items


async def create_pricing_plan(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    data: PricingPlanCreate,
) -> PricingPlansDB:
    async with transaction_context(engine, connection) as conn:
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
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    data: PricingPlanUpdate,
) -> PricingPlansDB | None:
    async with transaction_context(engine, connection) as conn:
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
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
) -> list[PricingPlanToServiceDB]:
    async with transaction_context(engine, connection) as conn:
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
                & (resource_tracker_pricing_plans.c.pricing_plan_id == pricing_plan_id)
            )
            .order_by(resource_tracker_pricing_plan_to_service.c.pricing_plan_id.desc())
        )
        result = await conn.execute(query)

        return [PricingPlanToServiceDB.model_validate(row) for row in result.fetchall()]


async def upsert_service_to_pricing_plan(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> PricingPlanToServiceDB:
    async with transaction_context(engine, connection) as conn:
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
                & (resource_tracker_pricing_plans.c.pricing_plan_id == pricing_plan_id)
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
                (resource_tracker_pricing_plans.c.pricing_plan_id == pricing_plan_id)
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
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    pricing_plan_id: PricingPlanId,
) -> list[PricingUnitsDB]:
    async with transaction_context(engine, connection) as conn:
        query = (
            _pricing_units_select_stmt()
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
                (resource_tracker_pricing_units.c.pricing_plan_id == pricing_plan_id)
                & (resource_tracker_pricing_unit_costs.c.valid_to.is_(None))
            )
            .order_by(resource_tracker_pricing_unit_costs.c.cost_per_unit.asc())
        )
        result = await conn.execute(query)

    return [PricingUnitsDB.model_validate(row) for row in result.fetchall()]


async def get_valid_pricing_unit(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    pricing_unit_id: PricingUnitId,
) -> PricingUnitsDB:
    async with transaction_context(engine, connection) as conn:
        query = (
            _pricing_units_select_stmt()
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
                (resource_tracker_pricing_units.c.pricing_plan_id == pricing_plan_id)
                & (resource_tracker_pricing_units.c.pricing_unit_id == pricing_unit_id)
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
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    data: PricingUnitWithCostCreate,
    pricing_plan_key: str,
) -> tuple[PricingUnitId, PricingUnitCostId]:
    async with transaction_context(engine, connection) as conn:
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
        try:
            result = await conn.execute(insert_stmt)
        except SqlAlchemyIntegrityError as exc:
            raise PricingUnitDuplicationError from exc
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
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    data: PricingUnitWithCostUpdate,
    pricing_plan_key: str,
) -> None:
    async with transaction_context(engine, connection) as conn:
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
                resource_tracker_pricing_units.c.pricing_unit_id == data.pricing_unit_id
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
                .returning(resource_tracker_pricing_unit_costs.c.pricing_unit_cost_id)
            )
            result = await conn.execute(insert_stmt)
            row = result.first()
            if row is None:
                raise PricingUnitCostNotCreatedDBError(data=data)


#################################
# Pricing unit-costs
#################################


async def get_pricing_unit_cost_by_id(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    pricing_unit_cost_id: PricingUnitCostId,
) -> PricingUnitCostsDB:
    async with transaction_context(engine, connection) as conn:
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
