# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import logging
from pathlib import Path

import pytest
from faker import Faker
from servicelib.file_utils import log_directory_changes, remove_directory

_logger = logging.getLogger(__name__)


@pytest.fixture
def some_dir(tmp_path, faker: Faker) -> Path:
    """Folder with some data, representing a given state"""
    base_dir = tmp_path / "original"
    base_dir.mkdir()
    (base_dir / "empty").mkdir()
    (base_dir / "d1").mkdir()
    (base_dir / "d1" / "f1").write_text(faker.text())
    (base_dir / "d1" / "f2").write_text(faker.text())
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
def a_file(tmp_path, faker: Faker) -> Path:
    base_dir = tmp_path / "other_folder"
    base_dir.mkdir()
    file_path = base_dir / "f1"
    file_path.write_text(faker.text())
    return file_path


async def test_remove_directory(some_dir: Path, only_children: bool) -> None:
    assert some_dir.exists() is True
    await remove_directory(
        path=some_dir, only_children=only_children, ignore_errors=True
    )
    assert some_dir.exists() is only_children


@pytest.mark.skip(
    "Not worth fixing until pytest fixes this issue https://github.com/pytest-dev/pytest/issues/6809"
)
async def test_remove_fail_fails(a_file: Path, only_children: bool) -> None:
    assert a_file.exists() is True

    with pytest.raises(NotADirectoryError) as excinfo:
        await remove_directory(path=a_file, only_children=only_children)

    assert excinfo.value.args[0] == f"Provided path={a_file} must be a directory"


async def test_remove_not_existing_directory(faker: Faker, only_children: bool) -> None:
    missing_path = Path(faker.file_path())
    assert missing_path.exists() is False
    await remove_directory(
        path=missing_path, only_children=only_children, ignore_errors=True
    )


@pytest.mark.skip(
    "Not worth fixing until pytest fixes this issue https://github.com/pytest-dev/pytest/issues/6809"
)
async def test_remove_not_existing_directory_rasing_error(
    faker: Faker, only_children: bool
) -> None:
    missing_path = Path(faker.file_path())
    assert missing_path.exists() is False
    with pytest.raises(FileNotFoundError):
        await remove_directory(
            path=missing_path, only_children=only_children, ignore_errors=False
        )


async def test_log_directory_changes(caplog: pytest.LogCaptureFixture, some_dir: Path):
    # directory cretion triggers no changes
    caplog.clear()
    with log_directory_changes(some_dir, _logger, logging.ERROR):
        (some_dir / "a-dir").mkdir(parents=True, exist_ok=True)
    assert "File changes in path" not in caplog.text
    assert "Files added:" not in caplog.text
    assert "Files removed:" not in caplog.text
    assert "File content changed" not in caplog.text

    # files were added
    caplog.clear()
    with log_directory_changes(some_dir, _logger, logging.ERROR):
        (some_dir / "hoho").touch()
    assert "File changes in path" in caplog.text
    assert "Files added:" in caplog.text
    assert "Files removed:" not in caplog.text
    assert "File content changed" not in caplog.text

    # files were removed
    caplog.clear()
    with log_directory_changes(some_dir, _logger, logging.ERROR):
        await remove_directory(path=some_dir)
    assert "File changes in path" in caplog.text
    assert "Files removed:" in caplog.text
    assert "Files added:" not in caplog.text
    assert "File content changed" not in caplog.text

    # nothing changed
    caplog.clear()
    with log_directory_changes(some_dir, _logger, logging.ERROR):
        pass
    assert caplog.text == ""

    # files added and removed
    caplog.clear()
    some_dir.mkdir(parents=True, exist_ok=True)
    (some_dir / "som_other_file").touch()
    with log_directory_changes(some_dir, _logger, logging.ERROR):
        (some_dir / "som_other_file").unlink()
        (some_dir / "som_other_file_2").touch()
    assert "File changes in path" in caplog.text
    assert "Files added:" in caplog.text
    assert "Files removed:" in caplog.text
    assert "File content changed" not in caplog.text

    # file content changed
    caplog.clear()
    (some_dir / "file_to_change").touch()
    with log_directory_changes(some_dir, _logger, logging.ERROR):
        (some_dir / "file_to_change").write_text("ab")
    assert "File changes in path" in caplog.text
    assert "Files added:" not in caplog.text
    assert "Files removed:" not in caplog.text
    assert "File content changed" in caplog.text
