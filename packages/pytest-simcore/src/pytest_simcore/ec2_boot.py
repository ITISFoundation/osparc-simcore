# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import contextlib
import os
import secrets
import signal
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Final

import pytest
from annotated_types import doc

from .helpers.bash_tools import create_link_to_tool_in_path, make_path_write_executable
from .helpers.typing_ec2_boot import BootScriptRunner

_EC2_BOOT_TOOLS: Final[Annotated[tuple[str, ...], doc("commands available before the boot script runs")]] = (
    "bash",
    "cat",
    "sleep",
    "timeout",
)


def _kill_process_group(process_group_id: int) -> None:
    """SIGKILL every process in the group, since killing only the shell would leave its children running"""
    with contextlib.suppress(ProcessLookupError):  # the group already exited on its own
        os.killpg(process_group_id, signal.SIGKILL)


@pytest.fixture
def run_as_if_in_ec2(tmp_path: Path) -> BootScriptRunner:
    """Run a bash script the way a booting EC2 machine would: with PATH holding only ``_EC2_BOOT_TOOLS``

    Scripts passed as ``executables`` are written into that PATH, so a stubbed ``docker`` is the machine's
    only docker. A command the machine would not have is not found there, which fails the script just as
    it would on a real machine.

    Raises ``subprocess.TimeoutExpired`` when the run outlives ``timeout``, after killing the script and
    everything it started.
    """

    def _run(
        script: str,
        executables: Mapping[str, str],
        env: Mapping[str, str] | None = None,
        *,
        timeout: float = 60,
    ) -> subprocess.CompletedProcess[str]:
        bin_dir = tmp_path / f"boot-{secrets.token_hex(4)}"
        bin_dir.mkdir()
        for tool in _EC2_BOOT_TOOLS:
            create_link_to_tool_in_path(bin_dir, tool)
        for name, content in executables.items():
            make_path_write_executable(bin_dir / name, content)

        # the shell leads its own process group so that a timeout can signal everything it started
        with subprocess.Popen(  # noqa: S603
            [str(bin_dir / "bash"), "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={"PATH": f"{bin_dir}", **(env or {})},
            start_new_session=True,
        ) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_process_group(process.pid)
                stdout, stderr = process.communicate()
                raise subprocess.TimeoutExpired(process.args, timeout, output=stdout, stderr=stderr) from None

        return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)

    return _run
