import re
from pathlib import Path
from typing import Annotated

import typer

from ..osparc_config import OSPARC_CONFIG_DIRNAME


def escape_dollar_brace(text: str) -> str:
    # the pattern finds '$${' that is not preceded by another '$'.
    pattern = r"(?<!\$)\$\${"
    replacement = "$$$${"
    return re.sub(pattern, replacement, text)


def legacy_escape(
    osparc_config_dirname: Annotated[
        Path,
        typer.Option(
            "--osparc-config-dirname",
            help="Path to where the .osparc configuration directory is located",
        ),
    ] = Path(OSPARC_CONFIG_DIRNAME),
):
    """
    Replaces all '$${' sequences with '$$$${' unless they are part of an
    existing '$$$${' sequence.
    """

    # NOTE: since https://github.com/docker/compose/releases/tag/v2.35.0
    # docker-compose was fixed/changed to escape `${}`
    # SEE https://github.com/docker/compose/pull/12664

    if not osparc_config_dirname.exists():
        msg = "Invalid path to metadata file or folder"
        raise typer.BadParameter(msg)

    for file in osparc_config_dirname.rglob("*.y*ml"):
        read_text = file.read_text()
        replaced_text = escape_dollar_brace(read_text)
        if read_text != replaced_text:
            print(f"Escaped sequence in {file}")
        file.write_text(replaced_text)
