from collections.abc import Iterator
from decimal import Decimal

import pytest
import sqlalchemy as sa
from faker import Faker
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanGet,
    PricingPlanToServiceGet,
    PricingUnitGet,
)
from models_library.resource_tracker import (
    PricingPlanClassification,
    PricingPlanCreate,
    PricingPlanUpdate,
    PricingUnitCostUpdate,
    PricingUnitWithCostCreate,
    PricingUnitWithCostUpdate,
    SpecificInfo,
    UnitExtraInfo,
)
from models_library.services import ServiceKey, ServiceVersion
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    pricing_plans,
    pricing_units,
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

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture()
def resource_tracker_setup_db(
    postgres_db: sa.engine.Engine,
) -> Iterator[None]:
    with postgres_db.connect() as con:

        yield

        con.execute(resource_tracker_pricing_unit_costs.delete())
        con.execute(resource_tracker_pricing_units.delete())
        con.execute(resource_tracker_pricing_plan_to_service.delete())
        con.execute(resource_tracker_pricing_plans.delete())


async def test_rpc_pricing_plans_workflow(
    mocked_redis_server: None,
    resource_tracker_setup_db: None,
    rpc_client: RabbitMQRPCClient,
    faker: Faker,
):
    _display_name = faker.word()
    result = await pricing_plans.create_pricing_plan(
        rpc_client,
        data=PricingPlanCreate(
            product_name="s4l",
            display_name=_display_name,
            description=faker.sentence(),
            classification=PricingPlanClassification.TIER,
            pricing_plan_key=faker.word(),
        ),
    )
    assert isinstance(result, PricingPlanGet)
    assert result.pricing_units == []
    assert result.display_name == _display_name
    _pricing_plan_id = result.pricing_plan_id

    _update_display_name = "display name updated"
    _update_description = "description name updated"
    result = await pricing_plans.update_pricing_plan(
        rpc_client,
        product_name="s4l",
        data=PricingPlanUpdate(
            pricing_plan_id=_pricing_plan_id,
            display_name=_update_display_name,
            description=_update_description,
            is_active=True,
        ),
    )
    assert isinstance(result, PricingPlanGet)
    assert result.pricing_units == []
    assert result.display_name == _update_display_name
    assert result.description == _update_description

    result = await pricing_plans.get_pricing_plan(
        rpc_client,
        product_name="s4l",
        pricing_plan_id=_pricing_plan_id,
    )
    assert isinstance(result, PricingPlanGet)
    assert result.pricing_units == []
    assert result.display_name == _update_display_name
    assert result.description == _update_description
    assert result.is_active is True

    result = await pricing_plans.list_pricing_plans(
        rpc_client,
        product_name="s4l",
    )
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], PricingPlanGet)
    assert result[0].pricing_units is None

    # Now I will deactivate the pricing plan
    result = await pricing_plans.update_pricing_plan(
        rpc_client,
        product_name="s4l",
        data=PricingPlanUpdate(
            pricing_plan_id=_pricing_plan_id,
            display_name=faker.word(),
            description=faker.sentence(),
            is_active=False,  # <-- deactivate
        ),
    )
    assert isinstance(result, PricingPlanGet)
    assert result.is_active is False


async def test_rpc_pricing_plans_with_units_workflow(
    mocked_redis_server: None,
    resource_tracker_setup_db: None,
    rpc_client: RabbitMQRPCClient,
    faker: Faker,
):
    _display_name = faker.word()
    result = await pricing_plans.create_pricing_plan(
        rpc_client,
        data=PricingPlanCreate(
            product_name="s4l",
            display_name=_display_name,
            description=faker.sentence(),
            classification=PricingPlanClassification.TIER,
            pricing_plan_key=faker.word(),
        ),
    )
    assert isinstance(result, PricingPlanGet)
    assert result.pricing_units == []
    assert result.display_name == _display_name
    _pricing_plan_id = result.pricing_plan_id

    result = await pricing_units.create_pricing_unit(
        rpc_client,
        product_name="s4l",
        data=PricingUnitWithCostCreate(
            pricing_plan_id=_pricing_plan_id,
            unit_name="SMALL",
            unit_extra_info=UnitExtraInfo.Config.schema_extra["examples"][0],
            default=True,
            specific_info=SpecificInfo(aws_ec2_instances=[]),
            cost_per_unit=Decimal(10),
            comment=faker.sentence(),
        ),
    )
    assert isinstance(result, PricingUnitGet)
    assert result
    _first_pricing_unit_id = result.pricing_unit_id
    _current_cost_per_unit_id = result.current_cost_per_unit_id

    # Get pricing plan
    result = await pricing_plans.get_pricing_plan(
        rpc_client,
        product_name="s4l",
        pricing_plan_id=_pricing_plan_id,
    )
    assert isinstance(result, PricingPlanGet)
    assert result.pricing_units
    assert len(result.pricing_units) == 1
    assert result.pricing_units[0].pricing_unit_id == _first_pricing_unit_id

    # Update only pricing unit info with COST update
    _unit_name = "VERY SMALL"
    result = await pricing_units.update_pricing_unit(
        rpc_client,
        product_name="s4l",
        data=PricingUnitWithCostUpdate(
            pricing_plan_id=_pricing_plan_id,
            pricing_unit_id=_first_pricing_unit_id,
            unit_name=_unit_name,
            unit_extra_info=UnitExtraInfo.Config.schema_extra["examples"][0],
            default=True,
            specific_info=SpecificInfo(aws_ec2_instances=[]),
            pricing_unit_cost_update=None,
        ),
    )
    assert isinstance(result, PricingUnitGet)
    assert result.unit_name == _unit_name
    assert result.current_cost_per_unit == Decimal(10)
    assert result.current_cost_per_unit_id == _current_cost_per_unit_id

    # Update pricing unit with COST update!
    result = await pricing_units.update_pricing_unit(
        rpc_client,
        product_name="s4l",
        data=PricingUnitWithCostUpdate(
            pricing_plan_id=_pricing_plan_id,
            pricing_unit_id=_first_pricing_unit_id,
            unit_name="MEDIUM",
            unit_extra_info=UnitExtraInfo.Config.schema_extra["examples"][0],
            default=True,
            specific_info=SpecificInfo(aws_ec2_instances=[]),
            pricing_unit_cost_update=PricingUnitCostUpdate(
                cost_per_unit=Decimal(15),
                comment="Comment update",
            ),
        ),
    )
    assert isinstance(result, PricingUnitGet)
    assert result.unit_name == "MEDIUM"
    assert result.current_cost_per_unit == Decimal(15)
    assert result.current_cost_per_unit_id != _current_cost_per_unit_id

    # Test get pricing unit
    result = await pricing_units.get_pricing_unit(
        rpc_client,
        product_name="s4l",
        pricing_plan_id=_pricing_plan_id,
        pricing_unit_id=_first_pricing_unit_id,
    )
    assert isinstance(result, PricingUnitGet)
    assert result.current_cost_per_unit == Decimal(15)

    # Create one more unit
    result = await pricing_units.create_pricing_unit(
        rpc_client,
        product_name="s4l",
        data=PricingUnitWithCostCreate(
            pricing_plan_id=_pricing_plan_id,
            unit_name="LARGE",
            unit_extra_info=UnitExtraInfo.Config.schema_extra["examples"][0],
            default=False,
            specific_info=SpecificInfo(aws_ec2_instances=[]),
            cost_per_unit=Decimal(20),
            comment=faker.sentence(),
        ),
    )
    assert isinstance(result, PricingUnitGet)
    assert result
    _second_pricing_unit_id = result.pricing_unit_id

    # Get pricing plan with units
    result = await pricing_plans.get_pricing_plan(
        rpc_client,
        product_name="s4l",
        pricing_plan_id=_pricing_plan_id,
    )
    assert isinstance(result, PricingPlanGet)
    assert result.pricing_units
    assert len(result.pricing_units) == 2
    assert result.pricing_units[0].pricing_unit_id == _first_pricing_unit_id
    assert result.pricing_units[1].pricing_unit_id == _second_pricing_unit_id


async def test_rpc_pricing_plans_to_service_workflow(
    mocked_redis_server: None,
    resource_tracker_setup_db: None,
    rpc_client: RabbitMQRPCClient,
    faker: Faker,
):
    result = await pricing_plans.create_pricing_plan(
        rpc_client,
        data=PricingPlanCreate(
            product_name="s4l",
            display_name=faker.word(),
            description=faker.sentence(),
            classification=PricingPlanClassification.TIER,
            pricing_plan_key=faker.word(),
        ),
    )
    assert isinstance(result, PricingPlanGet)
    _pricing_plan_id = result.pricing_plan_id

    result = (
        await pricing_plans.list_connected_services_to_pricing_plan_by_pricing_plan(
            rpc_client,
            product_name="s4l",
            pricing_plan_id=_pricing_plan_id,
        )
    )
    assert isinstance(result, list)
    assert result == []

    _first_service_version = ServiceVersion("2.0.2")
    result = await pricing_plans.connect_service_to_pricing_plan(
        rpc_client,
        product_name="s4l",
        pricing_plan_id=_pricing_plan_id,
        service_key=ServiceKey("simcore/services/comp/itis/sleeper"),
        service_version=_first_service_version,
    )
    assert isinstance(result, PricingPlanToServiceGet)
    assert result.pricing_plan_id == _pricing_plan_id
    assert result.service_version == _first_service_version

    result = (
        await pricing_plans.list_connected_services_to_pricing_plan_by_pricing_plan(
            rpc_client,
            product_name="s4l",
            pricing_plan_id=_pricing_plan_id,
        )
    )
    assert isinstance(result, list)
    assert len(result) == 1

    # Connect different version
    _second_service_version = ServiceVersion("3.0.0")
    result = await pricing_plans.connect_service_to_pricing_plan(
        rpc_client,
        product_name="s4l",
        pricing_plan_id=_pricing_plan_id,
        service_key=ServiceKey("simcore/services/comp/itis/sleeper"),
        service_version=_second_service_version,
    )
    assert isinstance(result, PricingPlanToServiceGet)
    assert result.pricing_plan_id == _pricing_plan_id
    assert result.service_version == _second_service_version

    result = (
        await pricing_plans.list_connected_services_to_pricing_plan_by_pricing_plan(
            rpc_client,
            product_name="s4l",
            pricing_plan_id=_pricing_plan_id,
        )
    )
    assert isinstance(result, list)
    assert len(result) == 2

    # Connect different service
    _different_service_key = ServiceKey("simcore/services/comp/itis/different-service")
    result = await pricing_plans.connect_service_to_pricing_plan(
        rpc_client,
        product_name="s4l",
        pricing_plan_id=_pricing_plan_id,
        service_key=_different_service_key,
        service_version=ServiceVersion("1.0.0"),
    )
    assert isinstance(result, PricingPlanToServiceGet)
    assert result.pricing_plan_id == _pricing_plan_id
    assert result.service_key == _different_service_key

    result = (
        await pricing_plans.list_connected_services_to_pricing_plan_by_pricing_plan(
            rpc_client,
            product_name="s4l",
            pricing_plan_id=_pricing_plan_id,
        )
    )
    assert isinstance(result, list)
    assert len(result) == 3
