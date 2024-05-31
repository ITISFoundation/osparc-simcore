from datetime import timedelta

from fastapi import FastAPI

from ._monitor import Monitor


def setup_status_monitor(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.status_monitor = monitor = Monitor(
            app, check_threshold=timedelta(seconds=1)
        )
        await monitor.setup()

    async def on_shutdown() -> None:
        monitor: Monitor = app.state.status_monitor
        await monitor.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
