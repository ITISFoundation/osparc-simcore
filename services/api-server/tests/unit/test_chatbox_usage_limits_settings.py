# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

from datetime import timedelta

import pytest
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_api_server.core.settings import ApplicationSettings


def test_usage_limits_disabled_when_not_configured(app_environment: EnvVarsDict):
    # ARRANGE / ACT - the base app environment does not configure usage limits
    settings = ApplicationSettings.create_from_envs()

    # ASSERT - enforcement is off: no limits block, no Redis needed
    assert settings.API_SERVER_CHATBOX_USAGE_LIMITS is None


def test_usage_limits_defaults_from_minimal_env(monkeypatch: pytest.MonkeyPatch, app_environment: EnvVarsDict):
    # ARRANGE - Redis endpoint + the (required) Provider Budget T$
    setenvs_from_dict(
        monkeypatch,
        {
            "API_SERVER_CHATBOX_USAGE_LIMITS": (
                '{"REDIS": {"REDIS_HOST": "simcore_redis", "REDIS_PASSWORD": "pass"}, "PROVIDER_BUDGET_USD": 1000}'
            )
        },
    )

    # ACT
    limits = ApplicationSettings.create_from_envs().API_SERVER_CHATBOX_USAGE_LIMITS

    # ASSERT - sensible defaults per spec
    assert limits is not None
    assert limits.ENABLED
    assert limits.REQUESTS_PER_MINUTE == 10
    assert limits.WINDOW_SPEND_USD == 0.20
    assert timedelta(hours=5) == limits.WINDOW_LENGTH
    assert limits.BLENDED_RATE_USD_PER_MTOK == 2.5
    assert limits.HARD_STOP_FRACTION == 0.9
    assert limits.RESERVATION_SAFETY_FACTOR == 1.5


def test_usage_limits_all_values_from_env(monkeypatch: pytest.MonkeyPatch, app_environment: EnvVarsDict):
    # ARRANGE
    setenvs_from_dict(
        monkeypatch,
        {
            "API_SERVER_CHATBOX_USAGE_LIMITS": (
                '{"REDIS": {"REDIS_HOST": "simcore_redis"}, "ENABLED": false, "REQUESTS_PER_MINUTE": 3,'
                ' "WINDOW_SPEND_USD": 1.5, "WINDOW_LENGTH": "2:00:00", "PROVIDER_BUDGET_USD": 800,'
                ' "HARD_STOP_FRACTION": 0.95, "BLENDED_RATE_USD_PER_MTOK": 3.25,'
                ' "RESERVATION_SAFETY_FACTOR": 2.0}'
            )
        },
    )

    # ACT
    limits = ApplicationSettings.create_from_envs().API_SERVER_CHATBOX_USAGE_LIMITS

    # ASSERT
    assert limits is not None
    assert not limits.ENABLED
    assert limits.REQUESTS_PER_MINUTE == 3
    assert limits.WINDOW_SPEND_USD == 1.5
    assert timedelta(hours=2) == limits.WINDOW_LENGTH
    assert limits.PROVIDER_BUDGET_USD == 800
    assert limits.HARD_STOP_FRACTION == 0.95
    assert limits.BLENDED_RATE_USD_PER_MTOK == 3.25
    assert limits.RESERVATION_SAFETY_FACTOR == 2.0


def test_usage_limits_hard_stop_fraction_validated(monkeypatch: pytest.MonkeyPatch, app_environment: EnvVarsDict):
    # ARRANGE - out-of-range hard stop
    setenvs_from_dict(
        monkeypatch,
        {"API_SERVER_CHATBOX_USAGE_LIMITS": '{"REDIS": {}, "HARD_STOP_FRACTION": 1.2}'},
    )

    # ACT / ASSERT
    with pytest.raises(Exception):  # noqa: B017, PT011
        ApplicationSettings.create_from_envs()
