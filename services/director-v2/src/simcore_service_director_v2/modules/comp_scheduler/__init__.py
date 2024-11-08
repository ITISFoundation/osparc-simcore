from fastapi import FastAPI

from ._base_scheduler import BaseCompScheduler
from ._task import on_app_shutdown, on_app_startup


def setup(app: FastAPI):
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))


__all__: tuple[str, ...] = (
    "setup",
    "BaseCompScheduler",
)
