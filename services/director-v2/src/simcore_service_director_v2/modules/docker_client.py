from dataclasses import dataclass

import aiodocker
from aiodocker import Docker
from fastapi import FastAPI
from servicelib.fastapi.app_state import SingletonInAppStateMixin


@dataclass
class SharedDockerClient(SingletonInAppStateMixin):
    app_state_name: str = "shared_docker_client"

    docker_client: Docker | None = None

    @classmethod
    def docker_instance(cls, app: FastAPI) -> Docker:
        docker_client = cls.get_from_app_state(app).docker_client
        assert docker_client is not None  # nosec
        return docker_client

    async def setup(self) -> None:
        self.docker_client = aiodocker.Docker()

    async def shutdown(self) -> None:
        if self.docker_client is not None:
            await self.docker_client.close()


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        shared_client = SharedDockerClient()
        await shared_client.setup()
        shared_client.set_to_app_state(app)

    async def on_shutdown() -> None:
        shared_client = SharedDockerClient.pop_from_app_state(app)
        await shared_client.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
