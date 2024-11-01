import asyncio
import logging
import os
import signal
import time
from asyncio.subprocess import Process
from typing import NamedTuple

import psutil
from common_library.error_codes import create_error_code
from servicelib.logging_errors import create_troubleshotting_log_kwargs

from ..modules.mounted_fs import MountedVolumes

HIDDEN_FILE_NAME = ".hidden_do_not_remove"

_logger = logging.getLogger(__name__)


class CommandResult(NamedTuple):
    success: bool
    message: str
    command: str
    elapsed: float | None

    def as_log_message(self) -> str:
        return (
            f"'{self.command}' finished_ok='{self.success}' "
            f"elapsed='{self.elapsed}'\n{self.message}"
        )


def _close_transport(proc: Process):
    # Closes transport (initialized during 'await proc.communicate(...)' ) and avoids error:
    #
    # Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7f871d0c7e50>
    # Traceback (most recent call last):
    #   File " ... .pyenv/versions/3.9.12/lib/python3.9/asyncio/base_subprocess.py", line 126, in __del__
    #     self.close()
    #

    # SEE implementation of asyncio.subprocess.Process._read_stream(...)
    for fd in (1, 2):
        # pylint: disable=protected-access
        if transport := getattr(proc, "_transport", None):  # noqa: SIM102
            if t := transport.get_pipe_transport(fd):
                t.close()


async def async_command(
    command: str,
    timeout: float | None = None,
    pipe_as_input: str | None = None,
    env_vars: dict[str, str] | None = None,
) -> CommandResult:
    """
    Does not raise Exception
    """
    proc = await asyncio.create_subprocess_shell(
        command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env_vars,
    )

    if pipe_as_input:
        assert proc.stdin  # nosec
        proc.stdin.write(pipe_as_input.encode())
        proc.stdin.close()

    start = time.time()

    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)

    except TimeoutError:
        proc.terminate()
        _close_transport(proc)

        # The SIGTERM signal is a generic signal used to cause program termination.
        # Unlike SIGKILL, this signal can be **blocked, handled, and ignored**.
        # It is the normal way to politely ask a program to terminate, i.e. giving
        # the opportunity to the underying process to perform graceful shutdown
        # (i.e. run shutdown events and cleanup tasks)
        #
        # SEE https://www.gnu.org/software/libc/manual/html_node/Termination-Signals.html
        #
        # There is a chance that the launched process ignores SIGTERM
        # in that case, it would proc.wait() forever. This code will be
        # used only to run docker compose CLI which behaves well. Nonetheless,
        # we add here some asserts.
        assert await proc.wait() == -signal.SIGTERM  # nosec
        assert not psutil.pid_exists(proc.pid)  # nosec

        _logger.warning(
            "Process %s timed out after %ss",
            f"{command=!r}",
            f"{timeout=}",
        )
        return CommandResult(
            success=False,
            message=f"Execution timed out after {timeout} secs",
            command=f"{command}",
            elapsed=time.time() - start,
        )

    except Exception as err:  # pylint: disable=broad-except

        error_code = create_error_code(err)
        user_error_msg = f"Unexpected error [{error_code}]"
        _logger.exception(
            **create_troubleshotting_log_kwargs(
                user_error_msg,
                error=err,
                error_context={"command": command, "proc.returncode": proc.returncode},
                error_code=error_code,
                tip="Process with command failed unexpectily",
            )
        )

        return CommandResult(
            success=False,
            message=user_error_msg,
            command=f"{command}",
            elapsed=time.time() - start,
        )

    # no exceptions
    return CommandResult(
        success=proc.returncode == os.EX_OK,
        message=stdout.decode(),
        command=f"{command}",
        elapsed=time.time() - start,
    )


async def volumes_fix_permissions(mounted_volumes: MountedVolumes) -> None:
    # NOTE: by creating a hidden file on all mounted volumes
    # the same permissions are ensured and avoids
    # issues when starting the services
    for volume_path in mounted_volumes.all_disk_paths_iter():
        hidden_file = volume_path / HIDDEN_FILE_NAME
        hidden_file.write_text(
            f"Directory must not be empty.\nCreated by {__file__}.\n"
            "Required by oSPARC internals to properly enforce permissions on this "
            "directory and all its files"
        )
