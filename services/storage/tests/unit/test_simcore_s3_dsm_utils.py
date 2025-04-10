from pathlib import Path

import pytest
from aws_library.s3._models import S3ObjectKey
from simcore_service_storage.utils.simcore_s3_dsm_utils import (
    UserSelectionStr,
    _strip_parent,
    compute_file_id_prefix,
    ensure_same_parent_in_user_selection,
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
        (Path("single_file"), Path("single_file"), "single_file"),
        (Path("single_folder"), Path("single_folder"), "single_folder"),
        (_FOLDERS_PATH / "folder", _FOLDERS_PATH / "folder", "folder"),
        (_FOLDERS_PATH / "a_file.txt", _FOLDERS_PATH / "a_file.txt", "a_file.txt"),
        (_FOLDERS_PATH, _FOLDERS_PATH / "the/actual/path", "the/actual/path"),
    ],
)
def test__strip_parent(selection: Path, s3_object: Path, expected: str):
    assert (
        _strip_parent(UserSelectionStr(f"{selection}"), S3ObjectKey(f"{s3_object}"))
        == expected
    )


@pytest.mark.parametrize(
    "user_slection, expected",
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
def test_ensure_same_parent_in_user_selection(
    user_slection: list[S3ObjectKey | Path], expected: bool
):
    assert (
        ensure_same_parent_in_user_selection([f"{x}" for x in user_slection])
        == expected
    )
