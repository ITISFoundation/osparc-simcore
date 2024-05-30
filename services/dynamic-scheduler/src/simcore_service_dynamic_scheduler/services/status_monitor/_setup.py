from fastapi import FastAPI


def setup_status_monitor(app: FastAPI) -> None:
    async def on_startup() -> None:
        pass

    async def on_shutdown() -> None:
        pass

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
