# pylint: disable=unused-argument
import os
from typing import Any, Dict

from settings_library.email import SMTPSettings
from simcore_service_webserver.login.plugin import LoginOptions


def test_smtp_settings(mock_env_devel_environment: Dict[str, Any]):

    settings = SMTPSettings()

    cfg = settings.dict(exclude_unset=True)

    for env_name in cfg:
        assert env_name in os.environ

    cfg = settings.dict()

    config = LoginOptions(**cfg)
    print(config.json(indent=1))

    assert config.SMTP_SENDER is not None
