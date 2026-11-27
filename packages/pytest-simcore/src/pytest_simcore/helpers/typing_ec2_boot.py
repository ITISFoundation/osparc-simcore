"""
Types for running a boot script the way a machine does while it starts up.

Used by the ``run_as_if_in_ec2`` fixture in ``pytest_simcore.ec2_boot``.
"""

import subprocess
from collections.abc import Mapping
from typing import Annotated, Protocol

from annotated_types import doc


class BootScriptRunner(Protocol):
    """Runs a bash script with a restricted set of executables, like a booting machine would"""

    def __call__(
        self,
        script: Annotated[str, doc("bash script to run, e.g. an EC2 user data script")],
        executables: Annotated[
            Mapping[str, str], doc("script content per command name, written into the restricted PATH")
        ],
        env: Annotated[
            Mapping[str, str] | None,
            doc("environment of the run, which replaces the environment of the test process"),
        ]
        | None = None,
        *,
        timeout: Annotated[float, doc("seconds before the run gets killed")] = 60,
    ) -> subprocess.CompletedProcess[str]: ...
