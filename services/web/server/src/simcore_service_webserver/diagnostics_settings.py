# pylint: disable=no-self-use
# pylint: disable=no-self-argument
from typing import Dict

from aiohttp.web import Application
from pydantic import Field, NonNegativeFloat, PositiveFloat, validator
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY, APP_SETTINGS_KEY
from settings_library.base import BaseCustomSettings


class DiagnosticsSettings(BaseCustomSettings):

    DIAGNOSTICS_SLOW_DURATION_SECS: PositiveFloat = Field(
        1.0,
        description=(
            "Any task blocked more than slow_duration_secs is logged as WARNING"
            "Aims to identify possible blocking calls"
        ),
        env=["DIAGNOSTICS_SLOW_DURATION_SECS", "AIODEBUG_SLOW_DURATION_SECS"],
    )

    DIAGNOSTICS_MAX_TASK_DELAY: PositiveFloat = Field(
        0.0,
        description="Sets an upper threshold for blocking functions, i.e. slow_duration_secs < max_task_delay",
    )

    DIAGNOSTICS_MAX_AVG_LATENCY: PositiveFloat = Field(
        3.0, description="Maximum average response latency in seconds"
    )

    DIAGNOSTICS_START_SENSING_DELAY: NonNegativeFloat = 60.0

    @validator("DIAGNOSTICS_MAX_TASK_DELAY", pre=True)
    @classmethod
    def validate_max_task_delay(cls, v, values):
        # Sets an upper threshold for blocking functions, i.e.
        # settings.DIAGNOSTICS_SLOW_DURATION_SECS  < settings.DIAGNOSTICS_MAX_TASK_DELAY
        #
        slow_duration_secs = float(values["DIAGNOSTICS_SLOW_DURATION_SECS"])
        return max(
            10 * slow_duration_secs,
            float(v),
        )  # secs


def get_plugin_settings(app: Application) -> DiagnosticsSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_DIAGNOSTICS
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, DiagnosticsSettings)  # nosec
    return settings


def get_diagnostics_config(app: Application) -> Dict:
    return app[APP_CONFIG_KEY].get("diagnostics", {})


def assert_valid_config(
    slow_duration_secs: float,
    max_avg_response_latency: float,
    start_sensing_delay: float,
    max_task_delay: float,
):
    WEBSERVER_DIAGNOSTICS = DiagnosticsSettings()

    assert (  # nosec
        WEBSERVER_DIAGNOSTICS.DIAGNOSTICS_SLOW_DURATION_SECS == slow_duration_secs
    )
    assert WEBSERVER_DIAGNOSTICS.DIAGNOSTICS_MAX_TASK_DELAY == max_task_delay  # nosec
    assert (  # nosec
        WEBSERVER_DIAGNOSTICS.DIAGNOSTICS_MAX_AVG_LATENCY == max_avg_response_latency
    )
    assert (  # nosec
        WEBSERVER_DIAGNOSTICS.DIAGNOSTICS_START_SENSING_DELAY == start_sensing_delay
    )

    return WEBSERVER_DIAGNOSTICS
