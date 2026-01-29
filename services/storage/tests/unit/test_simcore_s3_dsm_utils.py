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
    get_file_id_level,
    is_nested_level_file_id,
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
    assert _base_path_parent(UserSelectionStr(f"{selection}"), S3ObjectKey(f"{s3_object}")) == expected


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
def test_ensure_user_selection_from_same_base_directory(user_selection: list[S3ObjectKey | Path], expected: bool):
    assert ensure_user_selection_from_same_base_directory([f"{x}" for x in user_selection]) == expected


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
        (
            f"{_PID1}/{_NID1}/{_NID2}/something",
            f"project one/project one -> node one/{_NID2}/something",
        ),
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
        (
            f"{_PID2}/{_NID1}/{_NID2}/something",
            f"_project_two_/_project_two_->_node_one_/{_NID2}/something",
        ),
    ],
)
def test__replace_node_id_project_id_in_path(path: str, expected: str):
    assert _replace_node_id_project_id_in_path(_IDS_NAMES_MAP, path) == expected


@pytest.mark.parametrize(
    "file_id, expected_level",
    [
        # Empty and root cases
        ("", 1),  # Empty string splits to [""] which has length 1
        ("/", 1),  # Stripped to "" then split to [""] which has length 1
        ("//", 1),  # Stripped to "" then split to [""] which has length 1
        # Single component
        ("project_id", 1),
        ("api", 1),
        # Two components (root level)
        ("project_id/node_id", 2),
        ("api/node_id", 2),
        (
            "b21a3b80-d578-4b33-a224-e24ee2e4966a/42b9cc07-60f5-4d29-a063-176d1467901c",
            2,
        ),
        # Three components
        ("project_id/node_id/file.txt", 3),
        ("api/node_id/folder", 3),
        # Multiple components (deep nesting)
        ("project_id/node_id/folder/subfolder", 4),
        ("project_id/node_id/folder/subfolder/file.txt", 5),
        (
            "b21a3b80-d578-4b33-a224-e24ee2e4966a/42b9cc07-60f5-4d29-a063-176d1467901c/my/amazing/sub/folder/with/a/file.bin",
            9,
        ),
        (
            "api/42b9cc07-60f5-4d29-a063-176d1467901c/my/amazing/sub/folder/with/a/file.bin",
            9,
        ),
        # With leading/trailing slashes (should be stripped)
        ("/project_id/node_id/", 2),
        ("//project_id/node_id//", 2),
        ("/project_id/node_id/file.txt/", 3),
        # Edge cases with multiple consecutive slashes
        ("project_id//node_id", 3),  # Splits to ["project_id", "", "node_id"]
        ("project_id///node_id", 4),  # Splits to ["project_id", "", "", "node_id"]
        (
            "project_id/node_id//file.txt",
            4,
        ),  # Splits to ["project_id", "node_id", "", "file.txt"]
    ],
)
def test_get_file_id_level(file_id: str, expected_level: int):
    assert get_file_id_level(file_id) == expected_level


@pytest.mark.parametrize(
    "file_id, expected_is_nested",
    [
        # ROOT_FILE_ID_LEVELS = 3, so nested files have > 3 levels
        # Not nested (levels <= 3)
        ("", False),  # Level 1
        ("/", False),  # Level 1
        ("project_id", False),  # Level 1
        ("project_id/node_id", False),  # Level 2
        ("api/node_id", False),  # Level 2
        ("project_id/node_id/file.txt", False),  # Level 3 (exactly ROOT_FILE_ID_LEVELS)
        ("api/node_id/folder", False),  # Level 3
        (
            "b21a3b80-d578-4b33-a224-e24ee2e4966a/42b9cc07-60f5-4d29-a063-176d1467901c/file.txt",
            False,
        ),  # Level 3
        ("//project_id/node_id/folder//", False),  # Level 3 after stripping
        # Nested (levels > 3)
        ("project_id/node_id/folder/file.txt", True),  # Level 4
        ("project_id/node_id/folder/subfolder", True),  # Level 4
        ("project_id/node_id/folder/subfolder/file.txt", True),  # Level 5
        ("api/node_id/nested/folder/file.txt", True),  # Level 5
        (
            "b21a3b80-d578-4b33-a224-e24ee2e4966a/42b9cc07-60f5-4d29-a063-176d1467901c/my/amazing/sub/folder/with/a/file.bin",
            True,
        ),  # Level 9
        (
            "api/42b9cc07-60f5-4d29-a063-176d1467901c/my/amazing/sub/folder/with/a/file.bin",
            True,
        ),  # Level 9
        # With leading/trailing slashes
        ("/project_id/node_id/folder/file.txt/", True),  # Level 4 after stripping
        # Edge cases with multiple consecutive slashes
        (
            "project_id//node_id//file.txt",
            True,
        ),  # Level 4: ["project_id", "", "node_id", "", "file.txt"]
        (
            "project_id/node_id//folder/file.txt",
            True,
        ),  # Level 5: ["project_id", "node_id", "", "folder", "file.txt"]
        # Boundary cases (exactly at the threshold)
        ("project_id/node_id/exactly_three_levels", False),  # Level 3
        ("project_id/node_id/four/levels", True),  # Level 4
    ],
)
def test_is_nested_level_file_id(file_id: str, expected_is_nested: bool):
    assert is_nested_level_file_id(file_id) == expected_is_nested
