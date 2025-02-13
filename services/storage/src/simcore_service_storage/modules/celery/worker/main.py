from ....core.settings import ApplicationSettings
from ...celery.tasks import archive
from ..configurator import create_celery_app

settings = ApplicationSettings.create_from_envs()

app = create_celery_app(settings)

app.task(name="archive")(archive)


__all__ = ["app"]
