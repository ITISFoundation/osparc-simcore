import httpx
from fastapi import FastAPI
from simcore_service_autoscaling.core.settings import ApplicationSettings


async def test_background_task_runs(
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
    async_client: httpx.AsyncClient,
):
    assert app_settings.AUTOSCALING_POLL_INTERVAL
