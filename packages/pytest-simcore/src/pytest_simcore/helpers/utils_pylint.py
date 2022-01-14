""" Helps with running Pylint tests on different modules """
import os
import re
import subprocess
from pathlib import Path

AUTODETECT = 0
MATCH = re.compile(r"pdb.set_trace()")
EXCLUDE = ["__pycache__", ".git"]


def assert_pylint_is_passing(pylintrc, package_dir, number_of_jobs: int = AUTODETECT):
    """Runs Pylint with given inputs. In case of error some helpful Pylint messages are displayed

    This is used in different packages
    """
    command = (
        f"pylint --jobs={number_of_jobs} --rcfile {pylintrc} -v {package_dir}".split(
            " "
        )
    )
    with subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    ) as process:
        std_out, _ = process.communicate()
        if process.returncode != 0:
            assert (
                False
            ), f"Pylint failed with error\nExit code {process.returncode}\n{std_out.decode('utf-8')}"


def assert_no_pdb_in_code(code_dir: Path):
    # TODO: deprecate since Pylint 2.10 adds 'forgotten-debug-statement'
    # https://pylint.pycqa.org/en/latest/whatsnew/2.10.html?highlight=forgotten-debug-statement#new-checkers
    for root, dirs, files in os.walk(code_dir):
        for name in files:
            if name.endswith(".py"):
                pypth = Path(root) / name
                code = pypth.read_text()
                found = MATCH.findall(code)
                assert not found, "pbd.set_trace found in %s" % pypth
        dirs[:] = [d for d in dirs if d not in EXCLUDE]
