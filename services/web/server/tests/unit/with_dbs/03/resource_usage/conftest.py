# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from unittest.mock import MagicMock

import pytest
from faker import Faker
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanToServiceGet,
    RutPricingPlanGet,
    RutPricingPlanPage,
    RutPricingUnitGet,
)
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict

API_VERSION = "v0"
RESOURCE_NAME = "projects"
API_PREFIX = "/" + API_VERSION


DEFAULT_GARBAGE_COLLECTOR_INTERVAL_SECONDS: int = 3
DEFAULT_GARBAGE_COLLECTOR_DELETION_TIMEOUT_SECONDS: int = 3


def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    # print( ApplicationSettings.create_from_envs().model_dump_json((indent=1 )

    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_DB_LISTENER": "0",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_ANNOUNCEMENTS": "1",
        },
    )


@pytest.fixture
def mock_rpc_resource_usage_tracker_service_api(
    mocker: MockerFixture, faker: Faker
) -> dict[str, MagicMock]:
    return {
        ## Pricing plans
        "list_pricing_plans_without_pricing_units": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_service.pricing_plans.list_pricing_plans_without_pricing_units",
            autospec=True,
            return_value=RutPricingPlanPage(
                items=[
                    RutPricingPlanGet.model_validate(
                        RutPricingPlanGet.model_config["json_schema_extra"]["examples"][
                            0
                        ],
                    )
                ],
                total=1,
            ),
        ),
        "get_pricing_plan": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_service.pricing_plans.get_pricing_plan",
            autospec=True,
            return_value=RutPricingPlanGet.model_validate(
                RutPricingPlanGet.model_config["json_schema_extra"]["examples"][0],
            ),
        ),
        "create_pricing_plan": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_service.pricing_plans.create_pricing_plan",
            autospec=True,
            return_value=RutPricingPlanGet.model_validate(
                RutPricingPlanGet.model_config["json_schema_extra"]["examples"][0],
            ),
        ),
        "update_pricing_plan": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_service.pricing_plans.update_pricing_plan",
            autospec=True,
            return_value=RutPricingPlanGet.model_validate(
                RutPricingPlanGet.model_config["json_schema_extra"]["examples"][0],
            ),
        ),
        ## Pricing units
        "get_pricing_unit": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_service.pricing_units.get_pricing_unit",
            autospec=True,
            return_value=RutPricingUnitGet.model_validate(
                RutPricingUnitGet.model_config["json_schema_extra"]["examples"][0],
            ),
        ),
        "create_pricing_unit": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_service.pricing_units.create_pricing_unit",
            autospec=True,
            return_value=RutPricingUnitGet.model_validate(
                RutPricingUnitGet.model_config["json_schema_extra"]["examples"][0],
            ),
        ),
        "update_pricing_unit": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_service.pricing_units.update_pricing_unit",
            autospec=True,
            return_value=RutPricingUnitGet.model_validate(
                RutPricingUnitGet.model_config["json_schema_extra"]["examples"][0],
            ),
        ),
        ## Pricing plan to service
        "list_connected_services_to_pricing_plan_by_pricing_plan": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_service.pricing_plans.list_connected_services_to_pricing_plan_by_pricing_plan",
            autospec=True,
            return_value=[
                PricingPlanToServiceGet.model_validate(
                    PricingPlanToServiceGet.model_config["json_schema_extra"][
                        "examples"
                    ][0],
                )
            ],
        ),
        "connect_service_to_pricing_plan": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_service.pricing_plans.connect_service_to_pricing_plan",
            autospec=True,
            return_value=PricingPlanToServiceGet.model_validate(
                PricingPlanToServiceGet.model_config["json_schema_extra"]["examples"][
                    0
                ],
            ),
        ),
    }
