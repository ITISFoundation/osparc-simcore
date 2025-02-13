# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import datetime

import pytest
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_webserver.licenses.settings import LicensesSettings


def test_itis_vip_syncer_settings(
    mock_webserver_service_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):

    assert "LICENSES_ITIS_VIP_SYNCER_ENABLED" in mock_webserver_service_environment
    assert "LICENSES_ITIS_VIP_SYNCER_PERIODICITY" in mock_webserver_service_environment

    settings = LicensesSettings.create_from_envs()
    assert settings

    with monkeypatch.context() as patch:
        patch.setenv("LICENSES_ITIS_VIP_SYNCER_PERIODICITY", "1D02:03:04")

        settings: LicensesSettings = LicensesSettings.create_from_envs()
        assert settings
        assert settings.LICENSES_ITIS_VIP_SYNCER_PERIODICITY == datetime.timedelta(
            days=1, hours=2, minutes=3, seconds=4
        )
