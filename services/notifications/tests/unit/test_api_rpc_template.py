# pylint: disable=unused-argument

from typing import Any

import pytest
from models_library.notifications import Channel
from models_library.notifications.errors import (
    NotificationsTemplateContextValidationError,
    NotificationsTemplateNotFoundError,
)
from models_library.notifications.rpc import (
    PreviewTemplateResponse,
    TemplateRef,
)
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications import (
    preview_template,
    search_templates,
)

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]


async def test_search_templates_by_channel(
    rpc_client: RabbitMQRPCClient,
):
    all_templates = await search_templates(rpc_client, channel=None, template_name=None)
    if all_templates:
        channel = Channel.email
        filtered = await search_templates(rpc_client, channel=channel, template_name=None)
        # Check that all returned templates match the filter
        assert all(t.ref.channel == channel for t in filtered)
        # Check that filtered is a subset of all_templates
        assert all(template in all_templates for template in filtered)


async def test_search_templates_by_ref(
    rpc_client: RabbitMQRPCClient,
):
    all_templates = await search_templates(rpc_client, channel=None, template_name=None)
    if all_templates:
        channel = Channel.email
        template_name = "empty"
        filtered = await search_templates(rpc_client, channel=channel, template_name=template_name)
        assert len(filtered) == 1

        # Check that returned template match the filter
        assert filtered[0].ref.channel == channel
        assert filtered[0].ref.template_name == template_name


async def test_search_templates_non_existent(
    rpc_client: RabbitMQRPCClient,
):
    filtered = await search_templates(rpc_client, channel=None, template_name="non_existent_template")
    assert filtered == []


async def test_preview_template_success(
    fake_product_data: dict[str, str],
    rpc_client: RabbitMQRPCClient,
):
    templates = await search_templates(rpc_client, channel=Channel.email, template_name="empty")
    assert len(templates) == 1
    template = templates[0]
    ref = TemplateRef(**template.ref.model_dump())
    context = {
        "subject": "Test Email",
        "body": "This is a test email.",
    } | {"product": fake_product_data}

    response = await preview_template(rpc_client, ref=ref, context=context)
    assert isinstance(response, PreviewTemplateResponse)
    assert response.ref == template.ref
    assert isinstance(response.message_content, dict)


async def test_preview_template_not_found(
    rpc_client: RabbitMQRPCClient,
):
    ref = TemplateRef(
        channel=Channel.email,
        template_name="non_existent_template",
    )
    context = {}

    with pytest.raises(NotificationsTemplateNotFoundError):
        await preview_template(rpc_client, ref=ref, context=context)


async def test_preview_template_invalid_context(
    rpc_client: RabbitMQRPCClient,
):
    # Get available templates first
    templates = await search_templates(rpc_client, channel=None, template_name=None)
    if templates:
        template = templates[0]
        ref = TemplateRef(**template.ref.model_dump())
        context = {"invalid_key": "invalid_value"}  # Invalid context

        with pytest.raises((NotificationsTemplateContextValidationError,)):
            await preview_template(rpc_client, ref=ref, context=context)


async def test_preview_new_2fa_code_template_renders_without_errors(
    fake_product_data: dict[str, Any],
    rpc_client: RabbitMQRPCClient,
):
    ref = TemplateRef(channel=Channel.email, template_name="new_2fa_code")
    context = {
        "user": {
            "first_name": "John",
            "user_name": "john_doe",
        },
        "host": "https://example.com",
        "code": "123456",
        "product": fake_product_data,
    }

    response = await preview_template(rpc_client, ref=ref, context=context)
    assert isinstance(response, PreviewTemplateResponse)
    assert response.ref.template_name == "new_2fa_code"
    assert isinstance(response.message_content, dict)
    # Verify the rendered content contains the expected values
    assert "123456" in response.message_content["subject"]
    assert "John" in response.message_content["body_text"]
    assert "https://example.com" in response.message_content["body_text"]


async def test_preview_new_2fa_code_template_invalid_context(
    fake_product_data: dict[str, Any],
    rpc_client: RabbitMQRPCClient,
):
    ref = TemplateRef(channel=Channel.email, template_name="new_2fa_code")
    # Missing required fields 'user', 'host', 'code'
    context = {
        "invalid_key": "invalid_value",
        "product": fake_product_data,
    }

    with pytest.raises(NotificationsTemplateContextValidationError):
        await preview_template(rpc_client, ref=ref, context=context)


async def test_preview_paid_template_renders_without_errors(
    fake_product_data: dict[str, Any],
    rpc_client: RabbitMQRPCClient,
):
    ref = TemplateRef(channel=Channel.email, template_name="paid")
    context = {
        "user": {
            "first_name": "Jane",
            "last_name": "Doe",
            "user_name": "jane_doe",
            "email": "jane@example.com",
        },
        "payment": {
            "price_dollars": "25.00",
            "osparc_credits": "250.00",
            "invoice_url": "https://example.com/invoice/1",
        },
        "product": fake_product_data,
    }

    response = await preview_template(rpc_client, ref=ref, context=context)
    assert isinstance(response, PreviewTemplateResponse)
    assert response.ref.template_name == "paid"
    assert isinstance(response.message_content, dict)
    assert "25.00" in response.message_content["subject"]
    assert "250.00" in response.message_content["subject"]
    assert "Jane" in response.message_content["body_text"]


async def test_preview_paid_template_renders_with_optional_fields_missing(
    fake_product_data: dict[str, Any],
    rpc_client: RabbitMQRPCClient,
):
    ref = TemplateRef(channel=Channel.email, template_name="paid")
    context = {
        "user": {
            "user_name": "jdoe",
        },
        "payment": {
            "price_dollars": "10.00",
            "osparc_credits": "100.00",
            "invoice_url": "https://example.com/invoice/1",
        },
        "product": fake_product_data,
    }

    response = await preview_template(rpc_client, ref=ref, context=context)
    assert isinstance(response, PreviewTemplateResponse)
    assert response.ref.template_name == "paid"
    assert "jdoe" in response.message_content["body_text"]


async def test_preview_paid_template_invalid_context(
    fake_product_data: dict[str, Any],
    rpc_client: RabbitMQRPCClient,
):
    ref = TemplateRef(channel=Channel.email, template_name="paid")
    # Missing required 'user' and 'payment' fields
    context = {
        "invalid_key": "invalid_value",
        "product": fake_product_data,
    }

    with pytest.raises(NotificationsTemplateContextValidationError):
        await preview_template(rpc_client, ref=ref, context=context)
