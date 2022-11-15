from fastapi import FastAPI
from simcore_service_autoscaling.core.settings import ApplicationSettings


async def test_background_task_created(
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_POLL_INTERVAL
    assert hasattr(initialized_app.state, "autoscaler_task")
