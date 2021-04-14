#! /usr/bin/env python3

import asyncio
import pdb
import sys
from typing import Any, Dict, List

from httpx import URL, AsyncClient


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
    print("deleting project", project_id)
    r = await client.delete(path)
    print(r)


async def main(endpoint: URL, username: str, password: str) -> int:
    try:
        async with AsyncClient(base_url=endpoint.join("v0")) as client:
            await login_user(client, username, password)
            all_projects = await get_all_projects_for_user(client)
            if not all_projects:
                print("no projects found!")
                return 1
            print("number of projects to delete:", len(all_projects))
            await asyncio.gather(
                *[delete_project(client, prj["uuid"]) for prj in all_projects]
            )
            print(f"deleted {len(all_projects)}")
    except Exception as e:
        print("Unexpected issue:", type(e), str(e))
        return 1
    return 0


if __name__ == "__main__":
    print("Number of arguments:", len(sys.argv), "arguments.")
    print("Argument List:", str(sys.argv))
    endpoint = URL(sys.argv[1])
    username = sys.argv[2]
    password = sys.argv[3]
    sys.exit(
        asyncio.get_event_loop().run_until_complete(
            main(endpoint=endpoint, username=username, password=password)
        )
    )
