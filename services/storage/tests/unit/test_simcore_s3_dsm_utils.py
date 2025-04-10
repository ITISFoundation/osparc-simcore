from pathlib import Path
from typing import Final
from uuid import UUID

import pytest
from aws_library.s3._models import S3ObjectKey
from models_library.projects import ProjectID, ProjectIDStr
from models_library.projects_nodes_io import NodeIDStr
from simcore_service_storage.models import NodeID
from simcore_service_storage.utils.simcore_s3_dsm_utils import (
    UserSelectionStr,
    _base_path_parent,
    _replace_node_id_project_id_in_path,
    compute_file_id_prefix,
    ensure_user_selection_from_same_base_directory,
)


@pytest.mark.parametrize(
    "file_id, levels, expected",
    [
        (
            "b21a3b80-d578-4b33-a224-e24ee2e4966a/42b9cc07-60f5-4d29-a063-176d1467901c/my/amazing/sub/folder/with/a/file.bin",
            3,
            "b21a3b80-d578-4b33-a224-e24ee2e4966a/42b9cc07-60f5-4d29-a063-176d1467901c/my",
        ),
        (
            "api/42b9cc07-60f5-4d29-a063-176d1467901c/my/amazing/sub/folder/with/a/file.bin",
            3,
            "api/42b9cc07-60f5-4d29-a063-176d1467901c/my",
        ),
    ],
)
def test_compute_file_id_prefix(file_id, levels, expected):
    assert compute_file_id_prefix(file_id, levels) == expected


_FOLDERS_PATH = Path("nested/folders/path")


@pytest.mark.parametrize(
    "selection, s3_object, expected",
    [
        ("single_file", "single_file", "single_file"),
        ("single_folder", "single_folder", "single_folder"),
        ("a/b/c", "a/b/c/d/e/f/g", "c/d/e/f/g"),
        (_FOLDERS_PATH / "folder", _FOLDERS_PATH / "folder", "folder"),
        (_FOLDERS_PATH / "a_file.txt", _FOLDERS_PATH / "a_file.txt", "a_file.txt"),
        (_FOLDERS_PATH, _FOLDERS_PATH / "with/some/content", "path/with/some/content"),
    ],
)
def test__base_path_parent(selection: Path | str, s3_object: Path, expected: str):
    assert (
        _base_path_parent(UserSelectionStr(f"{selection}"), S3ObjectKey(f"{s3_object}"))
        == expected
    )


@pytest.mark.parametrize(
    "user_selection, expected",
    [
        ([], True),
        (["folder"], True),
        (["folder", "folder"], True),
        (["", ""], True),
        ([""], True),
        ([_FOLDERS_PATH / "a", _FOLDERS_PATH / "b"], True),
        (["a.txt", "b.txt"], True),
        (["a/a.txt"], True),
        # not same parent
        (["firsta/file", "second/file"], False),
        (["a/a.txt", "a.txt", "c.txt", "a/d.txt"], False),
    ],
)
def test_ensure_user_selection_from_same_base_directory(
    user_selection: list[S3ObjectKey | Path], expected: bool
):
    assert (
        ensure_user_selection_from_same_base_directory([f"{x}" for x in user_selection])
        == expected
    )


_PID1: Final[ProjectID] = UUID(int=1)
_PID2: Final[ProjectID] = UUID(int=2)
_NID1: Final[NodeID] = UUID(int=3)
_NID2: Final[NodeID] = UUID(int=4)
_IDS_NAMES_MAP: Final[dict[ProjectID, dict[ProjectIDStr | NodeIDStr, str]]] = {
    _PID1: {
        f"{_PID1}": "project one",
        f"{_NID1}": "project one -> node one",
        f"{_NID2}": "project one -> node two",
    },
    _PID2: {
        f"{_PID2}": "/project/two/",
        f"{_NID1}": "/project/two/->/node/one/",
        f"{_NID2}": "/project/two/->/node/two/",
    },
}


@pytest.mark.parametrize(
    "path, expected",
    [
        ("", ""),
        (f"{_PID1}", "project one"),
        (f"{_PID1}/{_NID1}", "project one/project one -> node one"),
        (f"{_PID1}/{_NID1}/something", "project one/project one -> node one/something"),
        (f"{_PID1}/{_NID1}/{_NID2}", f"project one/project one -> node one/{_NID2}"),
        (f"{_PID2}", "_project_two_"),
        (f"{_PID2}/{_NID1}", "_project_two_/_project_two_->_node_one_"),
        (
            f"{_PID2}/{_NID1}/something",
            "_project_two_/_project_two_->_node_one_/something",
        ),
        (
            f"{_PID2}/{_NID1}/{_NID2}",
            f"_project_two_/_project_two_->_node_one_/{_NID2}",
        ),
    ],
)
def test__replace_node_id_project_id_in_path(path: str, expected: str):
    assert _replace_node_id_project_id_in_path(_IDS_NAMES_MAP, path) == expected
