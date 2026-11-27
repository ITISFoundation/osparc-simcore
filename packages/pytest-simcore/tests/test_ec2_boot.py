# pylint:disable=redefined-outer-name
import subprocess
import time
from pathlib import Path

import pytest
from pytest_simcore.helpers.typing_ec2_boot import BootScriptRunner

pytest_plugins = ["pytest_simcore.ec2_boot"]

# background loop appending to a file, so a survivor of a timed out run keeps the file growing
_HEARTBEATING_CHILD = """#!/usr/bin/env bash
while :; do printf . >> "$HEARTBEAT_FILE"; sleep 0.2; done &
wait
"""


def test_run_as_if_in_ec2_kills_the_children_of_a_timed_out_script(run_as_if_in_ec2: BootScriptRunner, tmp_path: Path):
    """A timed out run must not leave background commands running behind the test"""
    heartbeat_path = tmp_path / "heartbeat"

    with pytest.raises(subprocess.TimeoutExpired):
        run_as_if_in_ec2(
            _HEARTBEATING_CHILD,
            {},
            {"HEARTBEAT_FILE": str(heartbeat_path)},
            timeout=1,
        )

    written_before_check = heartbeat_path.stat().st_size
    assert written_before_check > 0, "the background command never started"

    time.sleep(1)
    assert heartbeat_path.stat().st_size == written_before_check, (
        "a command started by the timed out script is still running"
    )
