# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any, Dict

import pytest
from models_library.service_settings import ServiceSetting, ServiceSettings


@pytest.mark.parametrize("example", ServiceSetting.Config.schema_extra["examples"])
def test_service_setting(example: Dict[str, Any]):
    service_setting_instance = ServiceSetting.parse_obj(example)
    assert service_setting_instance


def test_service_settings():
    service_settings_instance = ServiceSettings.parse_obj(
        ServiceSetting.Config.schema_extra["examples"]
    )
    assert service_settings_instance
