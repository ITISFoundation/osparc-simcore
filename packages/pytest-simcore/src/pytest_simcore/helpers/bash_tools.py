import secrets
import shutil
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final

import pytest


def make_path_write_executable(path: Path, content: str) -> None:
    """Write an executable script to ``path``"""
    path.write_text(content)
    path.chmod(0o755)


def create_link_to_tool_in_path(bin_dir: Path, tool: str) -> None:
    """Link ``tool`` from the current PATH into ``bin_dir``, so a script run with PATH=bin_dir sees it"""
    tool_path = shutil.which(tool)
    assert tool_path, f"{tool} not found in PATH"
    (bin_dir / tool).symlink_to(tool_path)


_EC2_BOOT_TOOLS: Final[tuple[str, ...]] = ("bash", "cat", "sleep", "timeout")


@pytest.fixture
def run_as_if_in_ec2(tmp_path: Path) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Run a bash script the way a booting EC2 machine would: with PATH holding only ``_EC2_BOOT_TOOLS``

    Scripts passed as ``executables`` are written into that PATH, so a stubbed ``docker`` is the machine's
    only docker. A command the machine would not have is not found there, which fails the script just as
    it would on a real machine.
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

        return subprocess.run(  # noqa: S603
            [str(bin_dir / "bash"), "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={"PATH": f"{bin_dir}", **(env or {})},
            check=False,
        )

    return _run
