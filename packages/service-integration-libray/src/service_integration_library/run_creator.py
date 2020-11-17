#!/bin/python

""" Creates a sh script that uses jq tool to retrieve variables
    to use in sh from a json file for use in an osparc service.

    Usage python run_creator --folder path/to/inputs.json --runscript path/to/put/the/script
:return: error code
"""


import argparse
import logging
import stat
import sys
from enum import IntEnum
from pathlib import Path
from typing import Dict

import yaml

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ExitCode(IntEnum):
    SUCCESS = 0
    FAIL = 1


def get_input_config(metadata_file: Path) -> Dict:
    inputs = {}
    with metadata_file.open() as fp:
        metadata = yaml.safe_load(fp)
        if "inputs" in metadata:
            inputs = metadata["inputs"]
    return inputs


def main(args=None) -> int:
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--metadata", help="The metadata yaml of the node",
                            type=Path, required=False, default="/metadata/metadata.yml")
        parser.add_argument(
            "--runscript", help="The run script", type=Path, required=True)
        options = parser.parse_args(args)

        # generate variables for input
        input_script = ["""
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
        input_config = get_input_config(options.metadata)
        for input_key, input_value in input_config.items():
            if "data:" in input_value["type"]:
                filename = input_key
                if "fileToKeyMap" in input_value and len(input_value["fileToKeyMap"]) > 0:
                    filename, _ = next(
                        iter(input_value["fileToKeyMap"].items()))
                input_script.append(
                    f"{str(input_key).upper()}=$INPUT_FOLDER/{str(filename)}")
                input_script.append(f"export {str(input_key).upper()}")
            else:
                input_script.append(
                    f"{str(input_key).upper()}=$(< \"$json_input\" jq '.{input_key}')")
                input_script.append(f"export {str(input_key).upper()}")

        input_script.extend(["""
exec execute.sh
        """
                             ])

        # write shell script
        shell_script = str("\n").join(input_script)
        options.runscript.write_text(shell_script)
        st = options.runscript.stat()
        options.runscript.chmod(st.st_mode | stat.S_IEXEC)
        return ExitCode.SUCCESS
    except:  # pylint: disable=bare-except
        log.exception("Unexpected error:")
        return ExitCode.FAIL


if __name__ == "__main__":
    sys.exit(main())
