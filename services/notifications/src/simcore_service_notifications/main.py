from simcore_service_notifications.core.application import create_app
from simcore_service_notifications.core.settings import ApplicationSettings

_settings = ApplicationSettings.create_from_envs()

the_app = create_app(_settings)
