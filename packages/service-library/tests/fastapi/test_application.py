import asyncio

from asgi_lifespan import LifespanManager
from fastapi import FastAPI


def _setup(app: FastAPI, index: int) -> None:
    async def startup() -> None:
        print(f"[{index}] startup")

    async def shutdown() -> None:
        print(f"[{index}] shutdown")

    app.add_event_handler("startup", startup)
    app.add_event_handler("startup", shutdown)


async def test_application_lifespan() -> None:
    app = FastAPI()

    for i in range(5):
        _setup(app, i)

    async with LifespanManager(app):
        print("DONE startup")
        await asyncio.sleep(1)
    print("DONE shutdown")
