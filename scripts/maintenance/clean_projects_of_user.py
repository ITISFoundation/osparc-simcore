#! /usr/bin/env python3

import asyncio
from typing import Any

import typer
from httpx import URL, AsyncClient, HTTPStatusError, Timeout, codes
from pydantic import EmailStr, SecretStr

DEFAULT_TIMEOUT = Timeout(30.0)


async def login_user(client: AsyncClient, email: EmailStr, password: SecretStr):
    path = "/auth/login"
    r = await client.post(
        path, json={"email": email, "password": password.get_secret_value()}
    )
    r.raise_for_status()


async def get_project_for_user(
    client: AsyncClient, project_id: str
) -> dict[str, Any] | None:
    path = f"/projects/{project_id}"
    r = await client.get(path, params={"type": "user"})
    if r.status_code == 200:
        response_dict = r.json()
        data = response_dict["data"]
        return data


async def get_all_projects_for_user(
    client: AsyncClient, next_link: str | None = None
) -> list[dict[str, Any]]:
    path = next_link if next_link else "/projects"
    r = await client.get(path, params={"type": "user"})
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
            f"deleting project {project_id} failed with status {r.status_code}: {r.reason_phrase}",
            fg=typer.colors.RED,
        )


async def clean(
    endpoint: URL, username: EmailStr, password: SecretStr, project_id: str | None
) -> int:
    try:
        async with AsyncClient(
            base_url=endpoint.join("v0"), timeout=DEFAULT_TIMEOUT
        ) as client:
            await login_user(client, username, password)
            all_projects = []
            if project_id:
                project = await get_project_for_user(client, project_id)
                if not project:
                    typer.secho(
                        f"project {project_id} not found!",
                        fg=typer.colors.RED,
                        err=True,
                    )
                    return 1
                all_projects = [project]
            if not all_projects:
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
            typer.secho("completed projects deletion", fg=typer.colors.YELLOW)
    except HTTPStatusError as exc:
        typer.secho(
            f"Responded with error  {exc.response.text}, [{type(exc)}]",
            fg=typer.colors.RED,
            err=True,
        )
        return 1

    except Exception as exc:  # pylint: disable=broad-except
        typer.secho(
            f"Unexpected issue: {exc}, [{type(exc)}]", fg=typer.colors.RED, err=True
        )
        return 1
    return 0


def main(
    endpoint: str, username: str, password: str, project_id: str | None = None
) -> int:
    return asyncio.get_event_loop().run_until_complete(
        clean(URL(endpoint), EmailStr(username), SecretStr(password), project_id)
    )


if __name__ == "__main__":
    typer.run(main)
