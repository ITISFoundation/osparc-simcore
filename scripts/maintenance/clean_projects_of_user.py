#! /usr/bin/env python3

import asyncio
import logging
import pdb
import sys
from typing import Any, Dict, List

import typer
from httpx import URL, AsyncClient

logger = logging.getLogger(__name__)


async def login_user(client: AsyncClient, email: str, password: str):
    path = "/auth/login"
    r = await client.post(path, json={"email": email, "password": password})


async def get_all_projects_for_user(client: AsyncClient) -> List[Dict[str, Any]]:
    path = "/projects"
    r = await client.get(path, params={"type": "user"}, timeout=30)
    if r.status_code == 200:
        return r.json()["data"]
    return []


async def delete_project(client: AsyncClient, project_id: str):
    path = f"/projects/{project_id}"
    logger.info("deleting project %s", project_id)
    r = await client.delete(path)
    if r.status_code != httpx.codes.OK:
        logger.error(
            "deleting project %s failed with status %s", project_id, r.status_code
        )


async def main(endpoint: str, username: str, password: str) -> int:
    try:
        async with AsyncClient(base_url=endpoint.join("v0")) as client:
            await login_user(client, username, password)
            all_projects = await get_all_projects_for_user(client)
            if not all_projects:
                logger.error("no projects found!")
                return 1
            logger.info("%s projects will be deleted...", len(all_projects))
            await asyncio.gather(
                *[delete_project(client, prj["uuid"]) for prj in all_projects]
            )
            logger.info("completed project deletion.")
    except Exception as e:
        logger.exception("Unexpected issue", exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    typer.run(main)
