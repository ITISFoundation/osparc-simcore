# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import logging
from unittest.mock import AsyncMock

import pytest
from models_library.notifications.rpc import SenderIdentity
from simcore_service_notifications.core.settings import NotificationsSMTPSettings
from simcore_service_notifications.services._smtp_config_check import (
    _build_status_table,
    check_smtp_configuration,
)


def _smtp_settings(*product_names: str) -> NotificationsSMTPSettings:
    return NotificationsSMTPSettings.model_validate(
        {
            "mail_servers": {
                "local": {"host": "mailpit", "port": 1025, "protocol": "UNENCRYPTED"},
            },
            "products": {
                name: {
                    "mail_server": "local",
                    "domain": f"{name}.test",
                    "extra_headers": {},
                    "local_parts": {"support": "support", "no_reply": "no-reply"},
                }
                for name in product_names
            },
        }
    )


@pytest.fixture
def product_repository() -> AsyncMock:
    repo = AsyncMock()
    repo.list_product_names.return_value = ["osparc", "s4l", "tis"]
    return repo


async def test_check_smtp_configuration_all_configured(
    product_repository: AsyncMock,
    caplog: pytest.LogCaptureFixture,
):
    smtp_settings = _smtp_settings("osparc", "s4l", "tis")

    with caplog.at_level(logging.INFO):
        await check_smtp_configuration(product_repository, smtp_settings)

    # A status table is logged
    assert "SMTP configuration status per product" in caplog.text
    assert "osparc" in caplog.text
    # Per-identity columns and resolved sender emails are shown
    for identity in SenderIdentity:
        assert f"{identity}" in caplog.text
    assert "support@osparc.test" in caplog.text
    assert "no-reply@osparc.test" in caplog.text
    # No warnings emitted
    assert not [r for r in caplog.records if r.levelno == logging.WARNING]


async def test_check_smtp_configuration_missing_products(
    product_repository: AsyncMock,
    caplog: pytest.LogCaptureFixture,
):
    smtp_settings = _smtp_settings("osparc")

    with caplog.at_level(logging.INFO):
        await check_smtp_configuration(product_repository, smtp_settings)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    warning_text = " ".join(r.getMessage() for r in warnings)
    assert "s4l" in warning_text
    assert "tis" in warning_text
    assert "osparc" not in warning_text


async def test_check_smtp_configuration_no_settings(
    product_repository: AsyncMock,
    caplog: pytest.LogCaptureFixture,
):
    with caplog.at_level(logging.INFO):
        await check_smtp_configuration(product_repository, None)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    warning_text = " ".join(r.getMessage() for r in warnings)
    for product_name in ("osparc", "s4l", "tis"):
        assert product_name in warning_text


def test_build_status_table_has_identity_columns_and_aligned_rows():
    smtp_settings = _smtp_settings("osparc")

    table = _build_status_table(["osparc", "tis"], smtp_settings)
    lines = table.splitlines()

    # header contains a column per SenderIdentity
    header = lines[1]
    assert "Product" in header
    assert "SMTP Configured" in header
    for identity in SenderIdentity:
        assert f"{identity}" in header

    # configured product shows resolved emails, missing one shows placeholders
    body = "\n".join(lines)
    assert "support@osparc.test" in body
    assert "no-reply@osparc.test" in body
    assert "—" in body  # placeholder for the unconfigured 'tis' product
