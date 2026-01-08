import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiodocker
from fastapi import FastAPI
from servicelib.fastapi.docker import get_remote_docker_client

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def docker_client(app: FastAPI) -> AsyncIterator[aiodocker.docker.Docker]:
    yield get_remote_docker_client(app)


async def swarm_get_number_nodes(app: FastAPI) -> int:
    async with docker_client(app) as client:
        nodes = await client.nodes.list()
        return len(nodes)


async def swarm_has_manager_nodes(app: FastAPI) -> bool:
    async with docker_client(app) as client:
        nodes = await client.nodes.list(filters={"role": "manager"})
        return bool(nodes)


async def swarm_has_worker_nodes(app: FastAPI) -> bool:
    async with docker_client(app) as client:
        nodes = await client.nodes.list(filters={"role": "worker"})
        return bool(nodes)
