# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any, Dict

import pytest
from models_library.service_settings import (
    SimcoreServiceSetting,
    SimcoreServiceSettings,
    SimcoreService,
)


@pytest.mark.parametrize(
    "example", SimcoreServiceSetting.Config.schema_extra["examples"]
)
def test_service_setting(example: Dict[str, Any]):
    service_setting_instance = SimcoreServiceSetting.parse_obj(example)
    assert service_setting_instance


def test_service_settings():
    service_settings_instance = SimcoreServiceSettings.parse_obj(
        SimcoreServiceSetting.Config.schema_extra["examples"]
    )
    assert service_settings_instance

    # ensure private attribute assignment
    for service_setting in service_settings_instance:
        # pylint: disable=protected-access
        service_setting._destination_container = "random_value"


SIMCORE_SERVICE_EXAMPLES = [
    (example, items, imdex)
    # pylint: disable=unnecessary-comprehension
    for example, items, imdex in zip(
        SimcoreService.Config.schema_extra["examples"],
        [1, 3, 5],
        ["legacy", "dynamic-service", "dynamic-service-with-compose-spec"],
    )
]


@pytest.mark.parametrize(
    "example, items",
    [(example, items) for example, items, _ in SIMCORE_SERVICE_EXAMPLES],
    ids=[i for _, _, i in SIMCORE_SERVICE_EXAMPLES],
)
def test_simcore_service_labels(example: Dict, items: int):
    simcore_service = SimcoreService.parse_obj(example)
    assert simcore_service
    assert len(simcore_service.dict(exclude_unset=True)) == items
