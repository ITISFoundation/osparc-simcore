from aiohttp.web import Application
from pydantic import (
    AliasChoices,
    Field,
    NonNegativeFloat,
    PositiveFloat,
    ValidationInfo,
    field_validator,
)
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from settings_library.base import BaseCustomSettings


class DiagnosticsSettings(BaseCustomSettings):
    DIAGNOSTICS_SLOW_DURATION_SECS: PositiveFloat = Field(
        default=1.0,
        description=(
            "Any task blocked more than slow_duration_secs is logged as WARNING"
            "Aims to identify possible blocking calls"
        ),
        validation_alias=AliasChoices(
            "DIAGNOSTICS_SLOW_DURATION_SECS", "AIODEBUG_SLOW_DURATION_SECS"
        ),
    )

    DIAGNOSTICS_HEALTHCHECK_ENABLED: bool = Field(
        default=False,
        description="Enables/disables healthcheck callback hook based on diagnostic sensors",
    )

    DIAGNOSTICS_MAX_TASK_DELAY: PositiveFloat = Field(
        default=0.0,
        description="Sets an upper threshold for blocking functions, "
        "i.e. slow_duration_secs < max_task_delay (healthcheck metric)",
    )

    DIAGNOSTICS_MAX_AVG_LATENCY: PositiveFloat = Field(
        default=3.0,
        description="Maximum average response latency in seconds (healthcheck metric)",
    )

    DIAGNOSTICS_START_SENSING_DELAY: NonNegativeFloat = 60.0

    @field_validator("DIAGNOSTICS_MAX_TASK_DELAY", mode="before")
    @classmethod
    def _validate_max_task_delay(cls, v, info: ValidationInfo):
        # Sets an upper threshold for blocking functions, i.e.
        # settings.DIAGNOSTICS_SLOW_DURATION_SECS  < settings.DIAGNOSTICS_MAX_TASK_DELAY
        #
        slow_duration_secs = float(info.data["DIAGNOSTICS_SLOW_DURATION_SECS"])
        return max(
            10 * slow_duration_secs,
            float(v),
        )  # secs


def get_plugin_settings(app: Application) -> DiagnosticsSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_DIAGNOSTICS
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, DiagnosticsSettings)  # nosec
    return settings
