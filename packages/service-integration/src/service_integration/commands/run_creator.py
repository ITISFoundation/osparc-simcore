import stat
from pathlib import Path

import typer
import yaml


def get_input_config(metadata_file: Path) -> dict:
    inputs = {}
    with metadata_file.open() as fp:
        metadata = yaml.safe_load(fp)
        if "inputs" in metadata:
            inputs = metadata["inputs"]
    return inputs


def main(
    metadata_file: Path = typer.Option(
        ".osparc/metadata.yml",
        "--metadata",
        help="The metadata yaml of the node",
    ),
    run_script_file_path: Path = typer.Option(
        ...,
        "--runscript",
        help="Path to the run script ",
    ),
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
        if "data:" in input_value["type"]:
            filename = input_key
            if "fileToKeyMap" in input_value and len(input_value["fileToKeyMap"]) > 0:
                filename, _ = next(iter(input_value["fileToKeyMap"].items()))
            input_script.append(
                f"{str(input_key).upper()}=$INPUT_FOLDER/{str(filename)}"
            )
            input_script.append(f"export {str(input_key).upper()}")
        else:
            input_script.append(
                f"{str(input_key).upper()}=$(< \"$json_input\" jq '.{input_key}')"
            )
            input_script.append(f"export {str(input_key).upper()}")

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


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
