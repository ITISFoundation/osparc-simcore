# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from types import SimpleNamespace

import pytest
import typer
from aiohttp import web
from common_library.basic_types import BootModeEnum
from pytest_mock import MockerFixture
from simcore_service_webserver import cli
from simcore_service_webserver.login import cli as login_cli


@pytest.mark.parametrize(
    "boot_mode,expected",
    [
        (BootModeEnum.DEBUG.value, True),
        (BootModeEnum.DEVELOPMENT.value, True),
        (BootModeEnum.LOCAL.value, True),
        (BootModeEnum.PRODUCTION.value, False),
        (BootModeEnum.DEFAULT.value, False),
        ("not-a-valid-mode", False),
        (None, False),
    ],
)
def test_is_devel_deployment(monkeypatch: pytest.MonkeyPatch, boot_mode: str | None, expected: bool):
    if boot_mode is None:
        monkeypatch.delenv("SC_BOOT_MODE", raising=False)
    else:
        monkeypatch.setenv("SC_BOOT_MODE", boot_mode)

    assert cli._is_devel_deployment() is expected  # noqa: SLF001


@pytest.mark.parametrize(
    "boot_mode",
    [BootModeEnum.DEBUG, BootModeEnum.DEVELOPMENT, BootModeEnum.LOCAL],
)
def test_ensure_development_deployment_passes_in_devel(mocker: MockerFixture, boot_mode: BootModeEnum):
    mocker.patch.object(
        login_cli,
        "get_application_settings",
        return_value=SimpleNamespace(SC_BOOT_MODE=boot_mode),
    )

    # does not raise
    login_cli._ensure_development_deployment(web.Application())  # noqa: SLF001


@pytest.mark.parametrize(
    "boot_mode",
    [BootModeEnum.PRODUCTION, BootModeEnum.DEFAULT, None],
)
def test_ensure_development_deployment_exits_otherwise(mocker: MockerFixture, boot_mode: BootModeEnum | None):
    mocker.patch.object(
        login_cli,
        "get_application_settings",
        return_value=SimpleNamespace(SC_BOOT_MODE=boot_mode),
    )

    with pytest.raises(typer.Exit) as exc_info:
        login_cli._ensure_development_deployment(web.Application())  # noqa: SLF001

    assert exc_info.value.exit_code == 1
