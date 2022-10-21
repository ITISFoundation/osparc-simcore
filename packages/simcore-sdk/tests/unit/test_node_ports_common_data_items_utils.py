# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest
from models_library.projects_nodes_io import SimcoreS3FileID
from simcore_sdk.node_ports_common.data_items_utils import create_simcore_file_id


@dataclass(frozen=True)
class _SimcoreFileIDParam:
    file_path: Path
    project_id: str
    node_id: str
    file_base_path: Optional[Path]
    expected_simcore_file_id: SimcoreS3FileID


@pytest.mark.parametrize(
    "params",
    [
        _SimcoreFileIDParam(
            file_path=Path("/some/random/file/path.ext"),
            project_id="2c471fb7-af17-408b-bcf4-91d419d0d20e",
            node_id="cd38bee6-9d4d-48e5-a8d5-98d7e049aa5e",
            file_base_path=None,
            expected_simcore_file_id=SimcoreS3FileID(
                "2c471fb7-af17-408b-bcf4-91d419d0d20e/cd38bee6-9d4d-48e5-a8d5-98d7e049aa5e/path.ext"
            ),
        ),
        _SimcoreFileIDParam(
            file_path=Path("/some/random/file/path.ext"),
            project_id="2c471fb7-af17-408b-bcf4-91d419d0d20e",
            node_id="cd38bee6-9d4d-48e5-a8d5-98d7e049aa5e",
            file_base_path=Path("/another/path"),
            expected_simcore_file_id=SimcoreS3FileID(
                "2c471fb7-af17-408b-bcf4-91d419d0d20e/cd38bee6-9d4d-48e5-a8d5-98d7e049aa5e/another/path/path.ext"
            ),
        ),
        _SimcoreFileIDParam(
            file_path=Path("/some/random/file/path.ext"),
            project_id="2c471fb7-af17-408b-bcf4-91d419d0d20e",
            node_id="cd38bee6-9d4d-48e5-a8d5-98d7e049aa5e",
            file_base_path=Path("/some/random"),
            expected_simcore_file_id=SimcoreS3FileID(
                "2c471fb7-af17-408b-bcf4-91d419d0d20e/cd38bee6-9d4d-48e5-a8d5-98d7e049aa5e/some/random/path.ext"
            ),
        ),
        _SimcoreFileIDParam(
            file_path=Path("/some/random/file/path.ext"),
            project_id="2c471fb7-af17-408b-bcf4-91d419d0d20e",
            node_id="cd38bee6-9d4d-48e5-a8d5-98d7e049aa5e",
            file_base_path=Path("/some/random/"),
            expected_simcore_file_id=SimcoreS3FileID(
                "2c471fb7-af17-408b-bcf4-91d419d0d20e/cd38bee6-9d4d-48e5-a8d5-98d7e049aa5e/some/random/path.ext"
            ),
        ),
        _SimcoreFileIDParam(
            file_path=Path("/some/random/file/path.ext"),
            project_id="2c471fb7-af17-408b-bcf4-91d419d0d20e",
            node_id="cd38bee6-9d4d-48e5-a8d5-98d7e049aa5e",
            file_base_path=Path("/some"),
            expected_simcore_file_id=SimcoreS3FileID(
                "2c471fb7-af17-408b-bcf4-91d419d0d20e/cd38bee6-9d4d-48e5-a8d5-98d7e049aa5e/some/path.ext"
            ),
        ),
    ],
)
def test_create_simcore_file_id(
    params: _SimcoreFileIDParam,
):
    simcore_file_id = create_simcore_file_id(
        params.file_path,
        params.project_id,
        params.node_id,
        file_base_path=params.file_base_path,
    )
    assert simcore_file_id == params.expected_simcore_file_id
