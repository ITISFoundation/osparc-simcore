#! /usr/bin/env python3

import asyncio
import os
from contextlib import suppress
from pathlib import Path

import typer
from httpx import URL, AsyncClient, HTTPStatusError
from pydantic.networks import EmailStr
from pydantic.types import SecretStr

EVERYONE_GROUP_ID = 1


def create_human_readable_message(exc: HTTPStatusError) -> str:
    msg = str(exc)
    with suppress(Exception):
        error = exc.response.json()["error"]
        for err in error["errors"]:
            msg += "\n{code}: {message}".format(**err)
    return msg


async def login_user(client: AsyncClient, email: EmailStr, password: SecretStr):
    typer.secho(
        f"loging user {email}",
    )
    path = "/auth/login"
    r = await client.post(
        path, json={"email": email, "password": password.get_secret_value()}
    )
    r.raise_for_status()
    typer.secho(
        f"user {email} logged in",
        fg=typer.colors.YELLOW,
    )


async def import_project(client: AsyncClient, project_file: Path) -> str:
    typer.secho(
        f"importing project {project_file}",
    )
    path = "/projects%3Aimport"
    files = {"fileName": open(project_file, mode="rb")}
    r = await client.post(path, files=files, timeout=20)
    r.raise_for_status()
    typer.secho(
        f"project {project_file} imported, received uuid is {r.json()['data']}",
        fg=typer.colors.YELLOW,
    )
    return r.json()["data"]["uuid"]


async def rename_project(client: AsyncClient, project_uuid: str, project_name: str):
    path = f"/projects/{project_uuid}"
    r = await client.get(path)
    r.raise_for_status()
    typer.secho(
        f"project {project_uuid} received, current name is {r.json()['data']['name']}",
    )

    modified_project = r.json()["data"]
    modified_project["name"] = project_name

    typer.secho(
        f"renaming project {project_uuid} to {project_name}",
        fg=typer.colors.YELLOW,
    )

    r = await client.put(path, json=modified_project)
    r.raise_for_status()
    typer.secho(
        f"project {project_uuid} renamed",
        fg=typer.colors.YELLOW,
    )


async def publish_as_template(client: AsyncClient, project_uuid: str) -> str:
    path = f"/projects/{project_uuid}"
    r = await client.get(path)
    r.raise_for_status()
    typer.secho(
        f"project {project_uuid} received, current name is {r.json()['data']['name']}",
    )

    # set access rights
    modified_project = r.json()["data"]
    modified_project["accessRights"].update(
        {"1": {"read": True, "write": False, "delete": False}}
    )

    path = "/projects"
    typer.secho(
        f"publishing project {project_uuid} as template...",
        fg=typer.colors.YELLOW,
    )
    r = await client.post(
        path,
        params={"from_study": project_uuid, "as_template": "true"},
        json=modified_project,
    )
    r.raise_for_status()
    typer.secho(
        f"project published as template {r.json()['data']['uuid']}",
        fg=typer.colors.YELLOW,
    )
    return r.json()["data"]["uuid"]


async def import_project_as_template(
    endpoint: URL,
    username: EmailStr,
    password: SecretStr,
    project_file: Path,
    project_name: str,
    share_with_gid: int,  # TODO: not used!?
) -> int:
    try:
        async with AsyncClient(base_url=endpoint.join("v0")) as client:
            await login_user(client, username, password)
            project_uuid = await import_project(client, project_file)
            await rename_project(client, project_uuid, project_name)
            template_uuid = await publish_as_template(client, project_uuid)
            typer.secho(
                f"project published as template! uuid [{template_uuid}]",
                fg=typer.colors.BRIGHT_WHITE,
            )

    except HTTPStatusError as exc:
        typer.secho(create_human_readable_message(exc), fg=typer.colors.RED, err=True)
        return os.EX_SOFTWARE

    except Exception as exc:  # pylint: disable=broad-except
        typer.secho(f"Unexpected issue: {exc}", fg=typer.colors.RED, err=True)
        return os.EX_SOFTWARE

    return os.EX_OK


def main(
    endpoint: str,
    username: str,
    project_file: Path,
    project_name: str | None = None,
    share_with_gid: int = EVERYONE_GROUP_ID,
    password: str = typer.Option(
        ..., prompt=True, confirmation_prompt=True, hide_input=True
    ),
) -> int:

    if project_name is None:
        project_name = project_file.name

    typer.secho(
        f"project {project_file} will be imported and named as {project_name}",
        fg=typer.colors.YELLOW,
    )

    return asyncio.get_event_loop().run_until_complete(
        import_project_as_template(
            URL(endpoint),
            EmailStr(username),
            SecretStr(password),
            project_file,
            project_name,
            share_with_gid,
        )
    )


if __name__ == "__main__":
    typer.run(main)
