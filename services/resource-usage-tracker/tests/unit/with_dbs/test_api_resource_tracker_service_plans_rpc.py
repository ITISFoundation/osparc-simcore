from collections.abc import Iterator
from decimal import Decimal

import pytest
import sqlalchemy as sa
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanGet,
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
)
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
):
    result = await pricing_plans.create_pricing_plan(
        rpc_client,
        data=PricingPlanCreate(
            product_name="s4l",
            display_name="Bla",
            description="bla",
            classification=PricingPlanClassification.TIER,
            pricing_plan_key="unique",
        ),
    )
    assert isinstance(result, PricingPlanGet)
    assert result.pricing_units == []
    assert result.display_name == "Bla"
    _pricing_plan_id = result.pricing_plan_id

    result = await pricing_plans.update_pricing_plan(
        rpc_client,
        product_name="s4l",
        data=PricingPlanUpdate(
            pricing_plan_id=_pricing_plan_id,
            display_name="blabla",
            description="blabla",
            is_active=True,
        ),
    )
    assert isinstance(result, PricingPlanGet)
    assert result.pricing_units == []
    assert result.display_name == "blabla"
    assert result.description == "blabla"

    result = await pricing_plans.get_pricing_plan(
        rpc_client,
        product_name="s4l",
        pricing_plan_id=_pricing_plan_id,
    )
    assert isinstance(result, PricingPlanGet)
    assert result.pricing_units == []
    assert result.display_name == "blabla"
    assert result.description == "blabla"

    # Now I will deactivate (maybe I should add is_active fielnd in the response)
    result = await pricing_plans.update_pricing_plan(
        rpc_client,
        product_name="s4l",
        data=PricingPlanUpdate(
            pricing_plan_id=_pricing_plan_id,
            display_name="blabla",
            description="blabla",
            is_active=False,
        ),
    )
    assert isinstance(result, PricingPlanGet)
    assert result.pricing_units == []


@pytest.mark.rpc_test()
async def test_rpc_pricing_plans_with_units_workflow(
    mocked_redis_server: None,
    resource_tracker_setup_db: None,
    rpc_client: RabbitMQRPCClient,
):
    result = await pricing_plans.create_pricing_plan(
        rpc_client,
        data=PricingPlanCreate(
            product_name="s4l",
            display_name="Bla",
            description="bla",
            classification=PricingPlanClassification.TIER,
            pricing_plan_key="unique",
        ),
    )
    assert isinstance(result, PricingPlanGet)
    assert result.pricing_units == []
    assert result.display_name == "Bla"
    _pricing_plan_id = result.pricing_plan_id

    result = await pricing_units.create_pricing_unit(
        rpc_client,
        product_name="s4l",
        data=PricingUnitWithCostCreate(
            pricing_plan_id=_pricing_plan_id,
            pricing_plan_key="",
            unit_name="SMALL",
            unit_extra_info={},
            default=True,
            specific_info=SpecificInfo(aws_ec2_instances=[]),
            cost_per_unit=Decimal(10),
            comment="Blabla",
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
    assert len(result.pricing_units) == 1
    assert result.pricing_units[0].pricing_unit_id == _first_pricing_unit_id

    # Update only pricing unit info with COST update
    result = await pricing_units.update_pricing_unit(
        rpc_client,
        product_name="s4l",
        data=PricingUnitWithCostUpdate(
            pricing_plan_id=_pricing_plan_id,
            pricing_unit_id=_first_pricing_unit_id,
            unit_name="MEDIUM",
            unit_extra_info={},
            default=True,
            specific_info=SpecificInfo(aws_ec2_instances=[]),
            pricing_unit_cost_update=None,
        ),
    )
    assert isinstance(result, PricingUnitGet)
    assert result.unit_name == "MEDIUM"
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
            unit_extra_info={},
            default=True,
            specific_info=SpecificInfo(aws_ec2_instances=[]),
            pricing_unit_cost_update=PricingUnitCostUpdate(
                cost_per_unit=Decimal(15),
                comment="Matus update",
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
            pricing_plan_key="a",
            unit_name="LARGE",
            unit_extra_info={},
            default=False,
            specific_info=SpecificInfo(aws_ec2_instances=[]),
            cost_per_unit=Decimal(20),
            comment="Blabla",
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
    assert len(result.pricing_units) == 2
    assert result.pricing_units[0].pricing_unit_id == _first_pricing_unit_id
    assert result.pricing_units[1].pricing_unit_id == _second_pricing_unit_id
