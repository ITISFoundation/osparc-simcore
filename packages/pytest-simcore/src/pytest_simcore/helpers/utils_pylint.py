""" Helps with running Pylint tests on different modules """
import subprocess
import re
from pathlib import Path
import os

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
    pipes = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    std_out, _ = pipes.communicate()
    if pipes.returncode != 0:
        assert (
            False
        ), f"Pylint failed with error\nExit code {pipes.returncode}\n{std_out.decode('utf-8')}"


def assert_no_pdb_in_code(code_dir: Path):
    for root, dirs, files in os.walk(code_dir):
        for name in files:
            if name.endswith(".py"):
                pypth = Path(root) / name
                code = pypth.read_text()
                found = MATCH.findall(code)
                assert not found, "pbd.set_trace found in %s" % pypth
        dirs[:] = [d for d in dirs if d not in EXCLUDE]
