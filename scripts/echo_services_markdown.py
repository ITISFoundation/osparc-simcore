#!/bin/env python
""" Usage

    cd osparc-simcore
    ./scripts/echo_services_markdown.py >services.md
"""

import itertools
import sys
from collections.abc import Iterable
from datetime import datetime
from operator import attrgetter
from pathlib import Path
from typing import Final, NamedTuple

CURRENT_FILE = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()
CURRENT_DIR = CURRENT_FILE.parent

_URL_PREFIX: Final[
    str
] = "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/refs/heads/master"

_REDOC_URL_PREFIX: Final[str] = f"https://redocly.github.io/redoc/?url={_URL_PREFIX}"
_SWAGGER_URL_PREFIX: Final[str] = f"https://petstore.swagger.io/?url={_URL_PREFIX}"


class CaptureTuple(NamedTuple):
    service_name: str
    file_path: Path


_service_names_aliases: dict[str, str] = {
    "web": "webserver",
}


def generate_markdown_table(
    *captured_files: Iterable[CaptureTuple],
) -> str:
    title = ("Name", "Files", "  ")
    num_cols = len(title)
    lines = ["-" * 10] * num_cols

    def _to_row_data(values: Iterable) -> list[str]:
        row = list(map(str, values))
        assert len(row) == num_cols, f"len({row=}) != {num_cols=}"
        return row

    rows = [
        _to_row_data(title),
        _to_row_data(lines),
    ]

    found = itertools.groupby(
        sorted(itertools.chain(*captured_files), key=attrgetter("service_name")),
        key=attrgetter("service_name"),
    )

    for name, service_files in found:
        rows.append(
            _to_row_data(
                (
                    f"**{name.upper()}**",
                    "",
                    "",
                )
            )
        )
        for _, file_path in service_files:
            linked_path = f"[{file_path}](./{file_path})"

            # SEE https://shields.io/badges
            badges = []

            if file_path.stem.lower() == "dockerfile":
                repo = _service_names_aliases.get(f"{name}") or name
                badges = [
                    f"[![Docker Image Size](https://img.shields.io/docker/image-size/itisfoundation/{repo})](https://hub.docker.com/r/itisfoundation/{repo}/tags)"
                ]

            elif file_path.stem.lower() == "openapi":
                badges = [
                    f"[![ReDoc](https://img.shields.io/badge/OpenAPI-ReDoc-85ea2d?logo=openapiinitiative)]({_REDOC_URL_PREFIX}/{file_path}) "
                    f"[![Swagger UI](https://img.shields.io/badge/OpenAPI-Swagger_UI-85ea2d?logo=swagger)]({_SWAGGER_URL_PREFIX}/{file_path})",
                ]

            rows.append(
                _to_row_data(
                    (
                        "",
                        linked_path,
                        " ".join(badges),
                    )
                )
            )
    rows.append(_to_row_data(["" * 10] * num_cols))

    # converts to markdown table
    return "\n".join(f"| {'|'.join(r)} |" for r in rows)


if __name__ == "__main__":

    repo_base_path = CURRENT_DIR.parent.resolve()
    services_path = repo_base_path / "services"

    def _to_tuple(file: Path):
        return CaptureTuple(
            f"{file.relative_to(services_path).parents[-2]}",
            file.relative_to(repo_base_path),
        )

    dockerfiles_found = (_to_tuple(file) for file in services_path.rglob("Dockerfile"))

    openapi_files_found = (
        _to_tuple(file)
        for file in services_path.rglob("openapi.*")
        if file.suffix in {".json", ".yaml", ".yml"}
    )

    markdown_table = generate_markdown_table(
        openapi_files_found,
        dockerfiles_found,
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("# services")
    print(">")
    print(f"> Auto generated on `{now}` using ")
    print("```cmd")
    print("cd osparc-simcore")
    print(f"python ./{CURRENT_FILE.relative_to(repo_base_path)}")
    print("```")
    print(markdown_table)
