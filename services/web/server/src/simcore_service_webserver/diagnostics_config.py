# pylint: disable=no-self-use
# pylint: disable=no-self-argument
from typing import Dict

from aiohttp.web import Application
from pydantic import BaseSettings, Field, NonNegativeFloat, PositiveFloat, validator
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY


class DiagnosticsSettings(BaseSettings):

    slow_duration_secs: PositiveFloat = Field(
        1.0,
        description=(
            "Any task blocked more than slow_duration_secs is logged as WARNING"
            "Aims to identify possible blocking calls"
        ),
        env="AIODEBUG_SLOW_DURATION_SECS",
    )

    max_task_delay: PositiveFloat = Field(
        0.0,
        description="Sets an upper threshold for blocking functions, i.e. slow_duration_secs < max_task_delay",
        env="DIAGNOSTICS_MAX_TASK_DELAY",
    )

    max_avg_response_latency: PositiveFloat = Field(
        3.0, env="DIAGNOSTICS_MAX_AVG_LATENCY"
    )

    start_sensing_delay: NonNegativeFloat = 60.0

    @validator("max_task_delay", pre=True)
    @classmethod
    def validate_max_task_delay(cls, v, values):
        slow_duration_secs = float(values["slow_duration_secs"])
        return max(
            10 * slow_duration_secs,
            float(v),
        )  # secs


def get_diagnostics_config(app: Application) -> Dict:
    return app[APP_CONFIG_KEY].get("diagnostics", {})
