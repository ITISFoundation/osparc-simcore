# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
import pytest
from asyncio import AbstractEventLoop
from pathlib import Path

from servicelib.file_utils import remove_directory


@pytest.fixture
def some_dir(tmp_path) -> Path:
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

    return base_dir


@pytest.fixture(params=[True, False])
def only_children(request) -> bool:
    return request.param


@pytest.fixture
def a_file(tmp_path) -> Path:
    base_dir = tmp_path / "other_folder"
    base_dir.mkdir()
    file_path = base_dir / "f1"
    file_path.write_text("o" * 100)
    return file_path


async def test_remove_directory(
    loop: AbstractEventLoop, some_dir: Path, only_children: bool
) -> None:
    assert some_dir.exists() is True
    await remove_directory(path=some_dir, only_children=only_children)
    assert some_dir.exists() is only_children


async def test_remove_fail_fails(
    loop: AbstractEventLoop, a_file: Path, only_children: bool
) -> None:
    assert a_file.exists() is True

    with pytest.raises(NotADirectoryError) as excinfo:
        await remove_directory(path=a_file, only_children=only_children)

    assert excinfo.value.args[0] == f"Provided path={a_file} must be a directory"
