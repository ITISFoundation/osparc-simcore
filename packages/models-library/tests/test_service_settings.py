# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any, Dict

import pytest
from models_library.service_settings import (
    SimcoreServiceSetting,
    SimcoreServiceSettings,
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
