# pylint: disable=redefined-outer-name
# pylint: disable=protected-access
# pylint: disable=unused-argument

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from faker import Faker
from pytest_mock.plugin import MockerFixture
from settings_library.r_clone import S3Provider
from simcore_sdk.node_ports_common import r_clone
from simcore_sdk.node_ports_common.r_clone import RCloneSettings


@pytest.fixture(params=list(S3Provider))
def s3_provider(request) -> S3Provider:
    return request.param


@pytest.fixture
def r_clone_settings(
    monkeypatch: pytest.MonkeyPatch, s3_provider: S3Provider, faker: Faker
) -> RCloneSettings:
    monkeypatch.setenv("R_CLONE_PROVIDER", s3_provider.value)
    monkeypatch.setenv("S3_ENDPOINT", faker.url())
    monkeypatch.setenv("S3_ACCESS_KEY", faker.pystr())
    monkeypatch.setenv("S3_SECRET_KEY", faker.pystr())
    monkeypatch.setenv("S3_BUCKET_NAME", faker.pystr())
    monkeypatch.setenv("S3_REGION", faker.pystr())
    return RCloneSettings.create_from_envs()


@pytest.fixture
def skip_if_r_clone_is_missing() -> None:  # noqa: PT004
    try:
        subprocess.check_output(["rclone", "--version"])  # noqa: S603, S607
    except Exception:  # pylint: disable=broad-except
        pytest.skip("rclone is not installed")


@pytest.fixture
def mock_async_r_clone_command(mocker: MockerFixture) -> Mock:
    mock = Mock()

    original_async_command = r_clone._async_r_clone_command  # noqa: SLF001

    async def _mock_async_command(*cmd: str, cwd: str | None = None) -> str:
        mock()
        return await original_async_command(*cmd, cwd=cwd)

    mocker.patch(
        "simcore_sdk.node_ports_common.r_clone._async_r_clone_command",
        side_effect=_mock_async_command,
    )

    return mock


async def test_is_r_clone_available_cached(
    r_clone_settings: RCloneSettings,
    mock_async_r_clone_command: Mock,
    skip_if_r_clone_is_missing: None,
) -> None:
    for _ in range(3):
        result = await r_clone.is_r_clone_available(r_clone_settings)
        assert type(result) is bool
    assert mock_async_r_clone_command.call_count == 1

    assert await r_clone.is_r_clone_available(None) is False


async def test__config_file(faker: Faker) -> None:
    text_to_write = faker.text()
    async with r_clone._config_file(text_to_write) as file_name:  # noqa: SLF001
        assert text_to_write == Path(file_name).read_text()
    assert Path(file_name).exists() is False


async def test__async_command_ok() -> None:
    result = await r_clone._async_r_clone_command("ls", "-la")  # noqa: SLF001
    assert len(result) > 0


@pytest.mark.parametrize(
    "cmd, exit_code, output",
    [
        (
            ["__i_do_not_exist__"],
            127,
            "/bin/sh: 1: __i_do_not_exist__: not found",
        ),
        (
            ["ls_", "-lah"],
            127,
            "/bin/sh: 1: ls_: not found",
        ),
        (
            ["echo", "this command will fail", "&&", "false"],
            1,
            "this command will fail",
        ),
    ],
)
async def test__async_command_error(
    cmd: list[str], exit_code: int, output: str
) -> None:
    with pytest.raises(r_clone.RCloneFailedError) as exe_info:
        await r_clone._async_r_clone_command(*cmd)  # noqa: SLF001
    assert (
        f"{exe_info.value}"
        == f"Command {' '.join(cmd)} finished with exit code={exit_code}:\n{output}\n"
    )


@pytest.fixture
def exclude_patterns_validation_dir(tmp_path: Path, faker: Faker) -> Path:
    """Directory with well known structure"""
    base_dir = tmp_path / "exclude_patterns_validation_dir"
    base_dir.mkdir()
    (base_dir / "empty").mkdir()
    (base_dir / "d1").mkdir()
    (base_dir / "d1" / "f1").write_text(faker.text())
    (base_dir / "d1" / "f2.txt").write_text(faker.text())
    (base_dir / "d1" / "sd1").mkdir()
    (base_dir / "d1" / "sd1" / "f1").write_text(faker.text())
    (base_dir / "d1" / "sd1" / "f2.txt").write_text(faker.text())

    return base_dir


EMPTY_SET: set[Path] = set()
ALL_ITEMS_SET: set[Path] = {
    Path("d1/f2.txt"),
    Path("d1/f1"),
    Path("d1/sd1/f1"),
    Path("d1/sd1/f2.txt"),
}


# + /exclude_patterns_validation_dir
#  + empty
#  + d1
#   - f2.txt
#   + sd1
#    - f2.txt
#    - f1
#   - f1
@pytest.mark.parametrize(
    "exclude_patterns, expected_result",
    [
        pytest.param({"/d1*"}, EMPTY_SET),
        pytest.param(
            {"/d1/sd1*"},
            {
                Path("d1/f2.txt"),
                Path("d1/f1"),
            },
        ),
        pytest.param(
            {"d1*"},
            EMPTY_SET,
        ),
        pytest.param(
            {"*d1*"},
            EMPTY_SET,
        ),
        pytest.param(
            {"*.txt"},
            {Path("d1/f1"), Path("d1/sd1/f1")},
        ),
        pytest.param(
            {"/absolute/path/does/not/exist*"},
            ALL_ITEMS_SET,
        ),
        pytest.param(
            {"/../../this/is/ignored*"},
            ALL_ITEMS_SET,
        ),
        pytest.param(
            {"*relative/path/does/not/exist"},
            ALL_ITEMS_SET,
        ),
        pytest.param(
            None,
            ALL_ITEMS_SET,
        ),
    ],
)
async def test__get_exclude_filter(
    skip_if_r_clone_is_missing: None,
    exclude_patterns_validation_dir: Path,
    exclude_patterns: set[str] | None,
    expected_result: set[Path],
):
    command: list[str] = [
        "rclone",
        "--quiet",
        "--dry-run",
        "--links",
        *r_clone._get_exclude_filters(exclude_patterns),  # noqa: SLF001
        "lsf",
        "--absolute",
        "--files-only",
        "--recursive",
        f"{exclude_patterns_validation_dir}",
    ]
    ls_result = await r_clone._async_r_clone_command(*command)  # noqa: SLF001
    relative_files_paths: set[Path] = {
        Path(x.lstrip("/")) for x in ls_result.split("\n") if x
    }
    assert relative_files_paths == expected_result
