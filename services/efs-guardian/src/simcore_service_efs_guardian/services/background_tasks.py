import logging

from fastapi import FastAPI

from ..core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


async def removal_policy_task(app: FastAPI) -> None:
    _logger.info("FAKE Removal policy task started (not yet implemented)")

    # After X days of inactivity remove data from EFS
    # Probably use `last_modified_data` in the project DB table
    # Maybe lock project during this time lock_project()

    app_settings: ApplicationSettings = app.state.settings
    assert app_settings  # nosec
