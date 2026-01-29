from fastapi import FastAPI

from .models import WakeupMessage


async def publish_wakeup(app: FastAPI, *, message: WakeupMessage) -> None:
    # Placeholder: publish via rabbit client or outbox
    _ = (app, message)


async def on_wakeup_message(app: FastAPI, *, message: WakeupMessage) -> None:
    # Placeholder: call worker.try_drain
    _ = (app, message)
