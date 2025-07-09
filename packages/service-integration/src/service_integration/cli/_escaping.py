import re
from pathlib import Path
from typing import Annotated

import typer

from ..osparc_config import OSPARC_CONFIG_DIRNAME


def escape_dollar_brace(text: str) -> str:
    """
    Replaces all '$${' sequences with '$$$${' unless they are part of an
    existing '$$$${' sequence.

    Args:
      text: The input string.

    Returns:
      The modified string. This function will NOT return None.
    """
    # The pattern finds '$${' that is not preceded by another '$'.
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
    """Escapes the `$${` with `$$$${` in all .y*ml files in the osparc config directory."""

    if not osparc_config_dirname.exists():
        msg = "Invalid path to metadata file or folder"
        raise typer.BadParameter(msg)

    print(f"checking files in {osparc_config_dirname}")

    for file in osparc_config_dirname.glob("*.y*ml"):
        print(f"scanning {file=}")
        read_text = file.read_text()
        replaced_text = escape_dollar_brace(read_text)
        if read_text != replaced_text:
            print(f"Escaped sequnce in {file}")
        file.write_text(replaced_text)
