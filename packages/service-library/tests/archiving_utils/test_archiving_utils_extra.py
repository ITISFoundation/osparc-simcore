# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import shutil
from pathlib import Path

import pytest
from helpers import print_tree
from servicelib.archiving_utils import (
    PrunableFolder,
    archive_dir,
    is_leaf_path,
    unarchive_dir,
)


@pytest.fixture
def state_dir(tmp_path) -> Path:
    """Folder with some data, representing a given state"""
    base_dir = tmp_path / "original"
    base_dir.mkdir()
    (base_dir / "empty").mkdir()
    (base_dir / "d1").mkdir()
    (base_dir / "d1" / "f1").write_text("o" * 100)
    (base_dir / "d1" / "f2").write_text("o" * 100)
    (base_dir / "d1" / "d1_1" / "d1_2").mkdir(parents=True, exist_ok=True)
    (base_dir / "d1" / "d1_1" / "f3").touch()
    (base_dir / "d1" / "d1_1" / "d1_2" / "f4").touch()
    (base_dir / "d1" / "d1_1" / "d1_1_1").mkdir(parents=True, exist_ok=True)
    (base_dir / "d1" / "d1_1" / "d1_1_1" / "f6").touch()

    print("state-dir ---")
    print_tree(base_dir)
    # + /tmp/pytest-of-crespo/pytest-95/test_override_and_prune_from_a1/original
    #  + empty
    #  + d1
    #   + d1_1
    #    + d2_2
    #     - f6
    #    - f3
    #    + d1_2
    #     - f4
    #   - f2
    #   - f1

    return base_dir


@pytest.fixture
def new_state_dir(tmp_path) -> Path:
    """Folder AFTER updated with new data"""
    base_dir = tmp_path / "updated"
    base_dir.mkdir()
    (base_dir / "d1").mkdir()
    (base_dir / "d1" / "f1").write_text("x")  # override
    (base_dir / "d1" / "f2").write_text("x")  # override
    # empty dir deleted
    (base_dir / "d1" / "d1_1" / "d1_2").mkdir(parents=True, exist_ok=True)
    # f3 and f4 are deleted
    (base_dir / "d1" / "d1_1" / "d1_2" / "f5").touch()  # new
    (base_dir / "d1" / "empty").mkdir()  # new
    # f6 deleted -> d1/d1_1/d2_2 remains empty and should be pruned

    print("new-state-dir ---")
    print_tree(base_dir)
    # + /tmp/pytest-of-crespo/pytest-95/test_override_and_prune_from_a1/updated
    #  + d1
    #   + d1_1
    #    + d1_2
    #     - f5
    #   - f2
    #   - f1
    #   + empty

    return base_dir


def test_override_and_prune_folder(state_dir: Path, new_state_dir: Path):
    """
    Test a concept that will be implemented in jupyter-commons
    Added here since in the latter there is no testing infrastructure and
    so it can be reused when code is moved into the new sidecar
    """

    expected_paths = {p.relative_to(new_state_dir) for p in new_state_dir.rglob("*")}

    # --------
    # 1) evaluate leafs to prune in paths tree

    old_paths = {p for p in state_dir.rglob("*") if is_leaf_path(p)}
    new_paths = {
        state_dir / p.relative_to(new_state_dir)
        for p in new_state_dir.rglob("*")
        if is_leaf_path(p)
    }
    to_delete = old_paths.difference(new_paths)

    # 2) override leafs from new_state_dir -> state_dir
    for p in new_state_dir.rglob("*"):
        if is_leaf_path(p):
            shutil.move(str(p), str(state_dir / p.relative_to(new_state_dir)))

    # 3) prune leafs that were not overriden
    for path in to_delete:
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()

    for p in state_dir.rglob("*"):
        if p.is_dir() and p not in new_paths and not any(p.glob("*")):
            p.rmdir()

    # -------
    got_paths = {p.relative_to(state_dir) for p in state_dir.rglob("*")}

    assert expected_paths == got_paths
    assert old_paths != got_paths

    print("after ----")
    print_tree(state_dir)


@pytest.mark.parametrize(
    "compress",
    [True, False],
)
async def test_override_and_prune_from_archive(
    tmp_path: Path,
    state_dir: Path,
    new_state_dir: Path,
    compress: bool,
):
    download_file = tmp_path / "download.zip"
    expected_paths = {
        p.relative_to(new_state_dir)
        for p in new_state_dir.rglob("*")
        if is_leaf_path(p)
    }

    # archive new_state_dir -> download.zip
    await archive_dir(
        dir_to_compress=new_state_dir,
        destination=download_file,
        compress=compress,
        store_relative_path=True,  # <=== relative!
    )

    folder = PrunableFolder(state_dir)

    # unarchive download.zip into state_dir
    unarchived = await unarchive_dir(
        archive_to_extract=download_file, destination_folder=state_dir
    )

    folder.prune(unarchived)

    after_relpaths = {
        p.relative_to(state_dir) for p in state_dir.rglob("*") if is_leaf_path(p)
    }

    assert after_relpaths != folder.before_relpaths
    assert after_relpaths == {p.relative_to(state_dir) for p in unarchived}
