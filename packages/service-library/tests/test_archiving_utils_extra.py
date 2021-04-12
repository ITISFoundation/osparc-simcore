# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import shutil
from pathlib import Path

import pytest
from servicelib.archiving_utils import archive_dir, unarchive_dir

# tests for leaf nodes in a paths tree
is_leaf_path = lambda p: p.is_file() or (p.is_dir() and not any(p.glob("*")))


def print_tree(path: Path, level=0):
    tab = " " * level
    print(f"{tab}- {path}")
    for p in path.rglob("*"):
        print_tree(p, level + 1)


@pytest.fixture
def state_dir(tmp_path) -> Path:
    """ Folder with some data, representing a given state"""
    base_dir = tmp_path / "original"
    base_dir.mkdir()
    (base_dir / "d1").mkdir()
    (base_dir / "d1" / "f1").write_text("o" * 100)
    (base_dir / "d1" / "f2").write_text("o" * 100)
    (base_dir / "empty").mkdir()
    (base_dir / "d1" / "d1_1" / "d1_2").mkdir(parents=True, exist_ok=True)
    (base_dir / "d1" / "d1_1" / "f3").touch()
    (base_dir / "d1" / "d1_1" / "d1_2" / "f4").touch()

    print("state-dir ---")
    print_tree(base_dir)

    return base_dir


@pytest.fixture
def new_state_dir(tmp_path) -> Path:
    """ Folder AFTER updated with new data """
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

    print("new-state-dir ---")
    print_tree(base_dir)

    return base_dir


def test_override_and_prune_folder(state_dir: Path, new_state_dir: Path):
    """
    Test a concept that will be implemented in jupyter-commons
    Added here since in the latter there is no testing infrastructure and
    so it can be reused when code is moved into the new sidecar
    """

    expected_paths = set(p.relative_to(new_state_dir) for p in new_state_dir.rglob("*"))

    # --------
    # 1) evaluate leafs to prune in paths tree

    old_paths = set(p for p in state_dir.rglob("*") if is_leaf_path(p))
    new_paths = set(
        state_dir / p.relative_to(new_state_dir)
        for p in new_state_dir.rglob("*")
        if is_leaf_path(p)
    )
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

    # -------
    got_paths = set(p.relative_to(state_dir) for p in state_dir.rglob("*"))

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
    expected_paths = set(
        p.relative_to(new_state_dir)
        for p in new_state_dir.rglob("*")
        if is_leaf_path(p)
    )

    # archive new_state_dir -> download.zip
    assert await archive_dir(
        dir_to_compress=new_state_dir,
        destination=download_file,
        compress=compress,
        store_relative_path=True,  # <=== relative!
    )

    before_relpaths = set(
        p.relative_to(state_dir) for p in state_dir.rglob("*") if is_leaf_path(p)
    )

    # unarchive download.zip into state_dir
    unarchived = await unarchive_dir(
        archive_to_extract=download_file, destination_folder=state_dir
    )

    # prune outdated leaf paths
    unarchived_relpaths = set(p.relative_to(state_dir) for p in unarchived)
    to_delete = before_relpaths.difference(unarchived_relpaths)
    for p in to_delete:
        path = state_dir / p
        assert path.exists()

        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()

    after_relpaths = set(
        p.relative_to(state_dir) for p in state_dir.rglob("*") if is_leaf_path(p)
    )

    assert after_relpaths != before_relpaths
    assert after_relpaths == unarchived_relpaths
