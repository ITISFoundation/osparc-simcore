#! /usr/bin/env python3

import asyncio
import logging
from typing import Any, Dict, List, Optional

import typer
from httpx import URL, AsyncClient, codes


async def login_user(client: AsyncClient, email: str, password: str):
    path = "/auth/login"
    r = await client.post(path, json={"email": email, "password": password})


async def get_all_projects_for_user(
    client: AsyncClient, next_link: Optional[str] = None
) -> List[Dict[str, Any]]:
    path = next_link if next_link else "/projects"
    r = await client.get(path, params={"type": "user"}, timeout=30)
    if r.status_code == 200:
        response_dict = r.json()
        data = response_dict["data"]
        next_link = response_dict.get("_links", {}).get("next", None)
        if next_link:
            data += await get_all_projects_for_user(client, next_link)
        return data
    return []


async def delete_project(client: AsyncClient, project_id: str, progressbar):
    path = f"/projects/{project_id}"
    r = await client.delete(path)
    progressbar.update(1)
    if r.status_code != codes.NO_CONTENT:
        typer.secho(
            f"deleting project {project_id} failed with status {r.status_code}",
            fg=typer.colors.RED,
        )


async def clean(endpoint: URL, username: str, password: str) -> int:
    try:
        async with AsyncClient(base_url=endpoint.join("v0")) as client:
            await login_user(client, username, password)
            all_projects = await get_all_projects_for_user(client)
            if not all_projects:
                typer.secho("no projects found!", fg=typer.colors.RED, err=True)
                return 1
            total = len(all_projects)
            typer.secho(f"{total} projects will be deleted...", fg=typer.colors.YELLOW)
            with typer.progressbar(
                length=total, label="deleting projects"
            ) as progressbar:
                await asyncio.gather(
                    *[
                        delete_project(client, prj["uuid"], progressbar)
                        for prj in all_projects
                    ]
                )
            typer.secho(f"completed projects deletion", fg=typer.colors.YELLOW)
    except Exception as exc:
        typer.secho(f"Unexpected issue: {exc}", fg=typer.colors.RED, err=True)
        return 1
    return 0


def main(endpoint: str, username: str, password: str) -> int:
    return asyncio.get_event_loop().run_until_complete(
        clean(URL(endpoint), username, password)
    )


if __name__ == "__main__":
    typer.run(main)
