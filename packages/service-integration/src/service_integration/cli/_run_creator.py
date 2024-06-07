import stat
from pathlib import Path
from typing import Annotated

import typer
import yaml

from ..osparc_config import OSPARC_CONFIG_DIRNAME, OSPARC_CONFIG_METADATA_NAME


def get_input_config(metadata_file: Path) -> dict:
    inputs = {}
    with metadata_file.open() as fp:
        metadata = yaml.safe_load(fp)
        if "inputs" in metadata:
            inputs = metadata["inputs"]
    return inputs


def run_creator(
    run_script_file_path: Annotated[
        Path,
        typer.Option(
            "--runscript",
            help="Path to the run script ",
        ),
    ],
    metadata_file: Annotated[
        Path,
        typer.Option(
            "--metadata",
            help="The metadata yaml of the node",
        ),
    ] = Path(f"{OSPARC_CONFIG_DIRNAME}/{OSPARC_CONFIG_METADATA_NAME}"),
):
    """Creates a sh script that uses jq tool to retrieve variables
    to use in sh from a json file for use in an osparc service (legacy).

    Usage python run_creator --folder path/to/inputs.json --runscript path/to/put/the/script

    """

    # generate variables for input
    input_script = [
        """
#!/bin/sh
#---------------------------------------------------------------
# AUTO-GENERATED CODE, do not modify this will be overwritten!!!
#---------------------------------------------------------------
# shell strict mode:
set -o errexit
set -o nounset
IFS=$(printf '\\n\\t')
cd "$(dirname "$0")"
json_input=$INPUT_FOLDER/inputs.json
    """
    ]
    input_config = get_input_config(metadata_file)
    for input_key, input_value in input_config.items():
        input_key_upper = f"{input_key}".upper()

        if "data:" in input_value["type"]:
            filename = input_key
            if "fileToKeyMap" in input_value and len(input_value["fileToKeyMap"]) > 0:
                filename, _ = next(iter(input_value["fileToKeyMap"].items()))
            input_script.append(f"{input_key_upper}=$INPUT_FOLDER/{filename}")
            input_script.append(f"export {input_key_upper}")
        else:
            input_script.append(
                f"{input_key_upper}=$(< \"$json_input\" jq '.{input_key}')"
            )
            input_script.append(f"export {input_key_upper}")

    input_script.extend(
        [
            """
exec execute.sh
    """
        ]
    )

    # write shell script
    shell_script = "\n".join(input_script)
    run_script_file_path.write_text(shell_script)
    st = run_script_file_path.stat()
    run_script_file_path.chmod(st.st_mode | stat.S_IEXEC)
