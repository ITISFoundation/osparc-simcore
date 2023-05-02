# pylint: disable=no-self-use
# pylint: disable=no-self-argument

from aiohttp.web import Application
from pydantic import Field, NonNegativeFloat, PositiveFloat, validator
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
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
