# pylint: disable=unused-argument

import pytest
from faker import Faker
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


async def test_preview_unregister_template(
    fake_product_data: dict[str, str],
    rpc_client: RabbitMQRPCClient,
    faker: Faker,
):
    templates = await search_templates(rpc_client, channel=Channel.email, template_name="unregister")
    assert len(templates) == 1

    ref = TemplateRef(**templates[0].ref.model_dump())
    context = {
        "user": {
            "first_name": faker.first_name(),
            "user_name": faker.user_name(),
        },
        "host": faker.domain_name(),
        "retention_days": 30,
        "product": fake_product_data,
    }

    response = await preview_template(rpc_client, ref=ref, context=context)
    assert isinstance(response, PreviewTemplateResponse)
    assert response.ref == templates[0].ref
    assert "subject" in response.message_content


async def test_preview_account_requested_template(
    fake_product_data: dict[str, str],
    rpc_client: RabbitMQRPCClient,
    faker: Faker,
):
    templates = await search_templates(rpc_client, channel=Channel.email, template_name="account_requested")
    assert len(templates) == 1

    ref = TemplateRef(**templates[0].ref.model_dump())
    context = {
        "host": faker.domain_name(),
        "product_info": {
            "name": "osparc",
            "display_name": "o²S²PARC",
            "vendor": {"name": "IT'IS Foundation"},
            "is_payment_enabled": False,
        },
        "request_form": {
            "firstName": faker.first_name(),
            "lastName": faker.last_name(),
            "email": faker.email(),
        },
        "ipinfo": {
            "x-real-ip": faker.ipv4(),
        },
        "product": fake_product_data,
    }

    response = await preview_template(rpc_client, ref=ref, context=context)
    assert isinstance(response, PreviewTemplateResponse)
    assert response.ref == templates[0].ref
    assert "subject" in response.message_content
