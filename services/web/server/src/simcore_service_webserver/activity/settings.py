from settings_library.base import BaseCustomSettings
from settings_library.prometheus import PrometheusSettings


class ActivitySettings(BaseCustomSettings):
    ACTIVITY_PROMETHEUS = PrometheusSettings
    # TODO: ACTIVITY_CELERY =
