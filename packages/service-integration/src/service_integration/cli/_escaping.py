from pathlib import Path
from typing import Annotated

import typer

from ..osparc_config import OSPARC_CONFIG_DIRNAME


def legacy_escape(
    osparc_config_dirname: Annotated[
        Path,
        typer.Option(
            "--osparc-config-dirname",
            help="Path to where the .osparc configuration directory is located",
        ),
    ] = Path(OSPARC_CONFIG_DIRNAME),
):
    """Escapes the `$${` with `$$$${` in all .y*ml files in the osparc config directory."""
    for file in osparc_config_dirname.glob("*.y*ml"):
        read_text = file.read_text()
        replaced_text = read_text.replace("$${", "$$$${")
        if read_text != replaced_text:
            print(f"Escaped sequnce in {file}")
        file.write_text(replaced_text)
