import typer
import asyncio
import httpx
from httpx import Response
from typing import Dict, List
from collections import deque


PREFIX_SERVICES_COMPUTATIONAL = "simcore/services/comp"
PREFIX_SERVICES_DYNAMIC = "simcore/services/dynamic"


async def _httpx_request(
    registry: str, user: str, password: str, path: str
) -> Response:
    params = {}
    if user and password:
        params["auth"] = (user, password)

    url = f"{registry}/v2/{path}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, **params)
        response.raise_for_status()
        return response


async def _compile_registry_report(
    registry: str, user: str, password: str
) -> Dict[str, List[str]]:
    response = await _httpx_request(registry, user, password, "_catalog")
    repositories = response.json()["repositories"]

    progressbar = typer.progressbar(length=len(repositories), label="fetching tags")

    async def _get_tag(repository: str) -> Dict:
        response = await _httpx_request(
            registry, user, password, f"{repository}/tags/list"
        )
        progressbar.update(1)
        return response.json()

    responses = await asyncio.gather(*[_get_tag(repo) for repo in repositories])

    progressbar.render_finish()

    repository_tags = {r["name"]: r["tags"] for r in responses}
    return repository_tags


def _format(
    repo_tags: Dict[str, List[str]], header_name: str, header_color: str
) -> str:
    service_header = typer.style(header_name, fg=typer.colors.WHITE, bg=header_color)
    service_list = "\n".join(f"- {k} {v}" for k, v in repo_tags.items())
    return f"{service_header}\n{service_list}\n"


def _format_print(
    computational: Dict[str, List[str]],
    dynamic: Dict[str, List[str]],
    other: Dict[str, List[str]],
) -> None:
    message = "\nListing services\n"

    if computational:
        message += _format(computational, "computational", typer.colors.GREEN)
    if dynamic:
        message += _format(dynamic, "dynamic", typer.colors.GREEN)
    if other:
        message += _format(other, "unexpected", typer.colors.RED)

    typer.echo(message)


def _format_repositories(repository_tags: Dict[str, List[str]]) -> None:
    computational: Dict[str, List[str]] = {}
    dynamic: Dict[str, List[str]] = {}
    other: Dict[str, List[str]] = {}

    for repo, tags in repository_tags.items():
        if repo.startswith(PREFIX_SERVICES_COMPUTATIONAL):
            computational[repo] = tags
        elif repo.startswith(PREFIX_SERVICES_DYNAMIC):
            dynamic[repo] = tags
        else:
            other[repo] = tags

    _format_print(computational, dynamic, other)


async def triage_registry(registry: str, user: str, password: str) -> None:
    repository_tags = await _compile_registry_report(
        registry=registry, user=user, password=password
    )
    _format_repositories(repository_tags)


def main(
    registry: str,
    user: str = typer.prompt("Registry user?", default=""),
    password: str = typer.prompt("Registry password?", default="", hide_input=True),
):
    asyncio.run(triage_registry(registry=registry, user=user, password=password))


if __name__ == "__main__":
    typer.run(main)
