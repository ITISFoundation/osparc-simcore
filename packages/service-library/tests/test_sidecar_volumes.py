from pathlib import Path
from typing import Final
from uuid import UUID, uuid4

import pytest
from servicelib.sidecar_volumes import VolumeInfo, VolumeUtils

NODE_ID: Final[UUID] = uuid4()
RUN_ID: Final[UUID] = uuid4()


def test_volume_utils_get_name():
    assert (
        VolumeUtils.get_name(Path("/tmp/a-path/Name with spaces"))
        == "_tmp_a-path_Name with spaces"
    )


@pytest.mark.parametrize(
    "path, node_id, run_id, expected",
    [
        (
            Path("/temp/store"),
            NODE_ID,
            RUN_ID,
            VolumeInfo(
                node_uuid=NODE_ID, run_id=RUN_ID, possible_volume_name="_temp_store"
            ),
        )
    ],
)
def test_to_from_source(path: Path, node_id: UUID, run_id: UUID, expected: VolumeInfo):
    source = VolumeUtils.get_source(path=path, node_uuid=node_id, run_id=run_id)

    assert VolumeUtils.get_volume_info(source) == expected
