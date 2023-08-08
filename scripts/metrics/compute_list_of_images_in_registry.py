#! /usr/bin/env python3

import asyncio
import json
from collections import defaultdict, deque
from datetime import date, datetime
from pathlib import Path
from pprint import pformat

import typer
from httpx import URL, AsyncClient

N = len("2020-10-09T12:28:14.7710")


async def get_repos(client):
    r = await client.get(
        "/_catalog",
    )
    r.raise_for_status()
    list_of_repositories = r.json()["repositories"]
    typer.secho(
        f"got the list of {len(list_of_repositories)} repositories from the registry"
    )
    filtered_list_of_repositories = list(
        filter(
            lambda repo: repo.startswith("simcore/services/dynamic/")
            or repo.startswith("simcore/services/comp/"),
            list_of_repositories,
        )
    )
    return filtered_list_of_repositories


async def list_images_in_registry(
    endpoint: URL,
    username: str,
    password: str,
    from_date: datetime | None,
    to_date: datetime,
) -> dict[str, list[tuple[str, str, str, str]]]:
    if not from_date:
        from_date = datetime(year=2000, month=1, day=1)
    typer.secho(
        f"listing images from {from_date} to {to_date} from {endpoint}",
        fg=typer.colors.YELLOW,
    )

    list_of_images_in_date_range = defaultdict(list)

    async with AsyncClient(
        base_url=endpoint.join("v2"), auth=(username, password), http2=True
    ) as client:
        list_of_repositories = await get_repos(client)

        with typer.progressbar(
            list_of_repositories, label="Processing repositories"
        ) as progress:
            for repo in progress:
                r = await client.get(f"/{repo}/tags/list")
                r.raise_for_status()
                list_of_tags = [tag for tag in r.json()["tags"] if tag != "latest"]

                # we go in reverse order, so the first that does not go in the date range will stop the loop
                for tag in reversed(list_of_tags):
                    r = await client.get(f"/{repo}/manifests/{tag}")
                    r.raise_for_status()
                    manifest = r.json()
                    # manifest[history] contains all the blobs, taking the latest one corresponds to the image creation date
                    history = manifest["history"]
                    tag_creation_dates = deque()
                    for blob in history:
                        v1_comp = json.loads(blob["v1Compatibility"])
                        tag_creation_dates.append(
                            datetime.strptime(
                                v1_comp["created"][:N], "%Y-%m-%dT%H:%M:%S.%f"
                            )
                        )
                    tag_last_date = sorted(tag_creation_dates)[-1]
                    # check this service is in the time range
                    if tag_last_date < from_date or tag_last_date > to_date:
                        break

                    # get the image labels from the last blob (same as director does)
                    v1_comp = json.loads(history[0]["v1Compatibility"])
                    container_config = v1_comp.get(
                        "container_config", v1_comp["config"]
                    )

                    simcore_labels = {}
                    for label_key, label_value in container_config["Labels"].items():
                        if label_key.startswith("io.simcore"):
                            simcore_labels.update(json.loads(label_value))

                    list_of_images_in_date_range[repo].append(
                        (
                            tag,
                            simcore_labels["name"],
                            simcore_labels["description"],
                            simcore_labels["type"],
                        )
                    )
        typer.secho(
            f"Completed. Found {len(list_of_images_in_date_range)} created between {from_date} and {to_date}",
            fg=typer.colors.YELLOW,
        )
        typer.secho(f"{pformat(list_of_images_in_date_range)}")

    return list_of_images_in_date_range


def main(
    endpoint: str,
    username: str,
    password: str = typer.Option(..., prompt=True, hide_input=True),
    from_date: datetime | None = typer.Option(None, formats=["%Y-%m-%d"]),
    to_date: datetime = typer.Option(f"{date.today()}", formats=["%Y-%m-%d"]),
    markdown: bool = typer.Option(False),
):
    endpoint_url = URL(endpoint)
    list_of_images: dict[str, list[tuple[str, str, str, str]]] = asyncio.run(
        list_images_in_registry(endpoint_url, username, password, from_date, to_date)
    )

    if markdown:
        output_file = Path.cwd() / f"{endpoint_url.host}.md"
        with output_file.open("w") as fp:
            fp.write(
                f"# {endpoint_url.host}: Services added between {from_date} and {to_date}\n\n"
            )
            fp.write("| Service | Version(s) | Name | Description | Type |\n")
            fp.write("| ------- | ---------- | ---- | ----------- | ---- |\n")
            for repo, repo_details in list_of_images.items():
                for index, (version, name, description, service_type) in enumerate(
                    repo_details
                ):
                    filtered_description = description.strip().replace("\n", "")
                    fp.write(
                        f"| {repo if index == 0 else ''} | {version} | {name if index == 0 else ''} | {filtered_description if index == 0 else ''} | {('Dynamic service' if service_type == 'dynamic' else 'Computational service') if index == 0 else ''} |\n"
                    )


if __name__ == "__main__":
    typer.run(main)
