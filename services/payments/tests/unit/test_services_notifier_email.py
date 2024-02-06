# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from pathlib import Path

import arrow
import pytest
from faker import Faker
from jinja2 import DictLoader, Environment, select_autoescape
from models_library.api_schemas_webserver.wallets import PaymentTransaction
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from settings_library.email import SMTPSettings
from simcore_service_payments.services.notifier_email import (
    _PRODUCT_NOTIFICATIONS_TEMPLATES,
    _add_attachments,
    _create_email_session,
    _create_user_email,
    _ProductData,
    _UserData,
)


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    external_environment: EnvVarsDict,
    docker_compose_service_payments_env_vars: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_payments_env_vars,
            **external_environment,
        },
    )


@pytest.fixture(scope="session")
def external_email(request: pytest.FixtureRequest) -> str | None:
    return request.config.getoption("--external-email", default=None)


@pytest.fixture
def user(faker: Faker, external_email: str | None):
    email = faker.email()
    if external_email:
        print("📧 EXTERNAL using in test", f"{external_email=}")
        email = external_email

    return _UserData(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        email=email,
    )


async def test_send_email_workflow(
    app_environment: EnvVarsDict,
    tmp_path: Path,
    faker: Faker,
    user: _UserData,
    external_email: str | None,
    mocker: MockerFixture,
):
    """
    Example of usage with external email and envfile

        > pytest --external-email=me@email.me --external-envfile=.myenv -k test_send_email_workflow  --pdb tests/unit
    """

    if not external_email:
        mocker.patch(
            "simcore_service_payments.services.notifier_email._create_email_session"
        )

    settings = SMTPSettings.create_from_envs()
    env = Environment(
        loader=DictLoader(_PRODUCT_NOTIFICATIONS_TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
    )

    product = _ProductData(
        product_name="osparc",
        display_name="o²S²PARC",
        vendor_display_inline="IT'IS Foundation. Zeughausstrasse 43, 8004 Zurich, Switzerland ",
        support_email="support@osparc.io",
    )
    payment = PaymentTransaction(
        payment_id="pt_123234",
        price_dollars=faker.pydecimal(positive=True, right_digits=2, left_digits=4),
        wallet_id=12,
        osparc_credits=faker.pydecimal(positive=True, right_digits=2, left_digits=4),
        comment="fake",
        created_at=arrow.now().datetime,
        completed_at=arrow.now().datetime,
        completedStatus="SUCCESS",
        state_message="ok",
        invoice_url=faker.image_url(),
    )

    msg = await _create_user_email(env, user, payment, product)

    attachment = tmp_path / "test-attachment.txt"
    attachment.write_text(faker.text())
    _add_attachments(msg, [attachment])

    print(msg)

    async with _create_email_session(settings) as smtp:
        await smtp.send_message(msg)
