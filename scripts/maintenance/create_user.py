#! /usr/bin/env python3

import asyncio

import typer
from httpx import URL, AsyncClient
from pydantic.networks import EmailStr
from pydantic.types import SecretStr


async def logout_current_user(client: AsyncClient):
    path = "/auth/logout"
    r = await client.post(path)
    r.raise_for_status()


async def register_user(client: AsyncClient, email: EmailStr, password: SecretStr):
    path = "/auth/register"
    await client.post(
        path,
        json={
            "email": email,
            "password": password.get_secret_value(),
            "confirm": password.get_secret_value(),
            "invitation": "",
        },
    )


async def create_user_with_password(
    endpoint: URL, username: EmailStr, password: SecretStr
) -> int:
    try:
        async with AsyncClient(base_url=endpoint.join("v0")) as client:
            typer.secho(
                f"registering user {username} with password {password}",
                fg=typer.colors.YELLOW,
            )
            await register_user(client, username, password)
            typer.secho(f"user registered", fg=typer.colors.YELLOW)
            await logout_current_user(client)
            typer.secho(f"registration done", fg=typer.colors.YELLOW)
    except Exception as exc:  # pylint: disable=broad-except
        typer.secho(f"Unexpected issue: {exc}", fg=typer.colors.RED, err=True)
        return 1
    return 0


def main(endpoint: str, username: str, password: str) -> int:
    return asyncio.get_event_loop().run_until_complete(
        create_user_with_password(
            URL(endpoint), EmailStr(username), SecretStr(password)
        )
    )


if __name__ == "__main__":
    typer.run(main)
