# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from simcore_service_webserver.groups import api as groups_service
from simcore_service_webserver.login._controller.rest._rest_exceptions import (
    _try_show_login_tip,
)
from simcore_service_webserver.products import products_service
from simcore_service_webserver.products.errors import ProductNotFoundError


def _create_fake_product(
    *,
    name: str,
    display_name: str = "",
    group_id: int | None,
    tip_products: list[str] | None = None,
) -> MagicMock:
    product = MagicMock()
    product.name = name
    product.display_name = display_name or name
    product.group_id = group_id
    product.vendor = {"marketing_tip_fallback_product_on_wrong_password": tip_products} if tip_products else {}
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


@pytest.mark.acceptance_test("For https://github.com/ITISFoundation/private-issues/issues/535")
async def test_tip_returns_preferred_product_display_name(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    # s4llite configured to suggest s4l; user belongs to s4l
    s4llite = _create_fake_product(name="s4llite", group_id=20, tip_products=["s4l", "osparc"])
    s4l = _create_fake_product(name="s4l", display_name="Sim4Life", group_id=10)
    osparc = _create_fake_product(name="osparc", display_name="o²S²PARC", group_id=30)
    _patch_products(monkeypatch, [s4llite, s4l, osparc])
    mock_is_user_in_group.return_value = True

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result == "Sim4Life"


async def test_tip_not_shown_when_no_tip_configured(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    # s4l has no tip configured
    s4l = _create_fake_product(name="s4l", group_id=10)
    s4llite = _create_fake_product(name="s4llite", group_id=20, tip_products=["s4l"])
    _patch_products(monkeypatch, [s4l, s4llite])
    mock_is_user_in_group.return_value = True

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="s4l")

    assert result is None


async def test_tip_not_shown_when_user_not_in_listed_products(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    # s4llite configured to check s4l, but user is NOT in s4l
    s4llite = _create_fake_product(name="s4llite", group_id=20, tip_products=["s4l"])
    s4l = _create_fake_product(name="s4l", display_name="Sim4Life", group_id=10)
    _patch_products(monkeypatch, [s4llite, s4l])
    mock_is_user_in_group.return_value = False

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result is None


async def test_tip_handles_db_error_gracefully(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    s4llite = _create_fake_product(name="s4llite", group_id=20, tip_products=["s4l"])
    s4l = _create_fake_product(name="s4l", display_name="Sim4Life", group_id=10)
    _patch_products(monkeypatch, [s4llite, s4l])
    mock_is_user_in_group.side_effect = RuntimeError("DB connection failed")

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result is None


async def test_tip_handles_missing_current_product_gracefully(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    _patch_products(monkeypatch, [])  # no products configured

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="unknown")

    assert result is None


async def test_tip_skips_listed_product_without_group_id(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    # s4llite configured to check s4l, but s4l has no group_id
    s4llite = _create_fake_product(name="s4llite", group_id=20, tip_products=["s4l"])
    s4l = _create_fake_product(name="s4l", display_name="Sim4Life", group_id=None)
    _patch_products(monkeypatch, [s4llite, s4l])
    mock_is_user_in_group.return_value = True

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result is None


async def test_tip_skips_unknown_listed_product(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    # s4llite lists "nonexistent" and "s4l"; nonexistent is skipped, user is in s4l
    s4llite = _create_fake_product(name="s4llite", group_id=20, tip_products=["s4l", "nonexistent"])
    s4l = _create_fake_product(name="s4l", display_name="Sim4Life", group_id=10)
    _patch_products(monkeypatch, [s4llite, s4l])
    mock_is_user_in_group.return_value = True

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    # preferred is s4l (first in list)
    assert result == "Sim4Life"
