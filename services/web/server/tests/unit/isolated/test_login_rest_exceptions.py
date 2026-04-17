# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from simcore_service_webserver.groups import api as groups_service
from simcore_service_webserver.login._controller.rest._rest_exceptions import (
    _should_show_login_tip,
)
from simcore_service_webserver.products import products_service
from simcore_service_webserver.products.errors import ProductNotFoundError


def _create_fake_product(
    *, name: str, group_id: int | None, marketing_login_tip_on_wrong_password: bool = False
) -> MagicMock:
    product = MagicMock()
    product.name = name
    product.group_id = group_id
    product.vendor = {"marketing_login_tip_on_wrong_password": True} if marketing_login_tip_on_wrong_password else {}
    return product


@pytest.fixture
def mock_app() -> web.Application:
    return web.Application()


@pytest.fixture
def mock_is_user_in_group(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock(return_value=False)
    monkeypatch.setattr(
        f"{groups_service.__name__}.is_user_in_group",
        mock,
    )
    return mock


def _patch_products(
    monkeypatch: pytest.MonkeyPatch,
    all_products: list[MagicMock],
) -> None:
    products_by_name = {p.name: p for p in all_products}

    def _get_product(_app: web.Application, product_name: str) -> MagicMock:
        if product_name not in products_by_name:
            raise ProductNotFoundError(product_name=product_name)
        return products_by_name[product_name]

    monkeypatch.setattr(
        f"{products_service.__name__}.get_product",
        _get_product,
    )
    monkeypatch.setattr(
        f"{products_service.__name__}.list_products",
        lambda _app: all_products,
    )


async def test_tip_shown_when_flag_enabled_and_user_in_other_product(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    # s4llite has the flag, s4l does not; user is in s4l
    s4llite = _create_fake_product(name="s4llite", group_id=20, marketing_login_tip_on_wrong_password=True)
    s4l = _create_fake_product(name="s4l", group_id=10)
    _patch_products(monkeypatch, [s4llite, s4l])
    mock_is_user_in_group.return_value = True

    result = await _should_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result is True


async def test_tip_not_shown_when_flag_disabled_on_current_product(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    # s4l does NOT have the flag; even if user is in another product
    s4l = _create_fake_product(name="s4l", group_id=10)
    s4llite = _create_fake_product(name="s4llite", group_id=20, marketing_login_tip_on_wrong_password=True)
    _patch_products(monkeypatch, [s4l, s4llite])
    mock_is_user_in_group.return_value = True

    result = await _should_show_login_tip(mock_app, user_id=42, product_name="s4l")

    assert result is False


async def test_tip_not_shown_when_user_not_in_any_other_product(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    # s4llite has the flag, but user is NOT in s4l
    s4llite = _create_fake_product(name="s4llite", group_id=20, marketing_login_tip_on_wrong_password=True)
    s4l = _create_fake_product(name="s4l", group_id=10)
    _patch_products(monkeypatch, [s4llite, s4l])
    mock_is_user_in_group.return_value = False

    result = await _should_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result is False


async def test_tip_not_shown_when_other_product_also_has_flag(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    # Both products have the flag — user in both, but tip should NOT show
    s4llite = _create_fake_product(name="s4llite", group_id=20, marketing_login_tip_on_wrong_password=True)
    s4l = _create_fake_product(name="s4l", group_id=10, marketing_login_tip_on_wrong_password=True)
    _patch_products(monkeypatch, [s4llite, s4l])
    mock_is_user_in_group.return_value = True

    result = await _should_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result is False


async def test_tip_handles_db_error_gracefully(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    s4llite = _create_fake_product(name="s4llite", group_id=20, marketing_login_tip_on_wrong_password=True)
    s4l = _create_fake_product(name="s4l", group_id=10)
    _patch_products(monkeypatch, [s4llite, s4l])
    mock_is_user_in_group.side_effect = RuntimeError("DB connection failed")

    result = await _should_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result is False


async def test_tip_handles_missing_product_gracefully(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    _patch_products(monkeypatch, [])  # no products configured

    result = await _should_show_login_tip(mock_app, user_id=42, product_name="unknown")

    assert result is False


async def test_tip_skips_other_product_without_group_id(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    # s4llite has the flag, s4l has no group_id — can't check membership
    s4llite = _create_fake_product(name="s4llite", group_id=20, marketing_login_tip_on_wrong_password=True)
    s4l = _create_fake_product(name="s4l", group_id=None)
    _patch_products(monkeypatch, [s4llite, s4l])
    mock_is_user_in_group.return_value = True

    result = await _should_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result is False
