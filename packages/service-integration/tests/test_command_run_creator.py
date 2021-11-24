# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import os
from pathlib import Path
from pprint import pformat

from service_integration import __version__


def test_version(run_program_with_args):
    result = run_program_with_args("--version")
    assert result.exit_code == os.EX_OK
    assert __version__ in result.output


def test_make_service_cli_run(run_program_with_args, metadata_file_path: Path):
    """
    service.cli/run: $(metatada)
        # Updates adapter script from metadata in $<
        osparc-service-integrator run-creator --metadata $< --runscript $@
    """
    run_script_path: Path = metadata_file_path.parent / "run"

    assert not run_script_path.exists()

    result = run_program_with_args(
        "run-creator",
        "--metadata",
        str(metadata_file_path),
        "--runscript",
        run_script_path,
    )
    assert result.exit_code == os.EX_OK

    generated_code = run_script_path.read_text()
    expected_snippet = set(
        """
    set -o errexit
    set -o nounset
    IFS=$(printf '\n\t')
    cd "$(dirname "$0")"
    json_input=$INPUT_FOLDER/inputs.json

    INPUT_1=$INPUT_FOLDER/input_1
    export INPUT_1

    exec execute.sh
    """
    )

    expected_snippet.discard("\t")
    assert expected_snippet.issubset(
        set(generated_code)
    ), f"Got \n{pformat(generated_code)}"
