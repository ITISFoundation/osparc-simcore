# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import sys
from pathlib import Path

import pytest
from simcore_service_dynamic_sidecar.core.utils import CommandResult, async_command

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture
def cmd(tmp_path: Path, sleep: int):
    docker_compose = tmp_path / "docker_compose.yml"
    docker_compose.write_text(
        f"""\
services:
  my-container:
    environment:
      - DY_SIDECAR_PATH_INPUTS=/work/inputs
      - DY_SIDECAR_PATH_OUTPUTS=/work/outputs
      - DY_SIDECAR_STATE_PATHS=["/work/workspace"]
    working_dir: /work
    image: busybox:latest
    command: sh -c "echo 'setup'; sleep {sleep}; echo 'teardown'"
    """
    )

    print("docker-compose from cmd fixture:\n", docker_compose.read_text(), "\n")
    return f"docker compose -f {docker_compose} up"


@pytest.mark.parametrize(
    "sleep,timeout,expected_success", [(1, 10, True), (10, 2, False)]
)
async def test_async_command_with_timeout(
    cmd: str, sleep: int, timeout: int, expected_success: bool
):
    result: CommandResult = await async_command(cmd, timeout)

    assert result.success == expected_success, result
