"""
    Collection of functions that create fake raw data that can be used
    to populate postgres DATABASE, create datasets with consistent values, etc

    Built on top of the idea of Faker library (https://faker.readthedocs.io/en/master/),
    that generate fake data to bootstrap a database, fill-in stress tests, anonymize data ...
    etc

    NOTE: all outputs MUST be Dict-like or built-in data structures that fit at least
    required fields in postgres_database.models tables or pydantic models.
"""


import itertools
import json
import random
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Final
from uuid import uuid4

import faker
from faker import Faker
from simcore_postgres_database.models.api_keys import api_keys
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.groups import groups
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)
from simcore_postgres_database.models.products import Vendor, products
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_postgres_database.webserver_models import GroupType, UserStatus

_STATES = [
    StateType.NOT_STARTED,
    StateType.PENDING,
    StateType.RUNNING,
    StateType.SUCCESS,
    StateType.FAILED,
]


DEFAULT_FAKER: Final = faker.Faker()


def _compute_hash(password: str) -> str:
    try:
        # 'passlib' will be used only if already installed.
        # This way we do not force all modules to install
        # it only for testing.
        import passlib.hash

        return passlib.hash.sha256_crypt.using(rounds=1000).hash(password)

    except ImportError:
        # if 'passlib' is not installed, we will use a library
        # from the python distribution for convenience
        import hashlib

        return hashlib.sha224(password.encode("ascii")).hexdigest()


DEFAULT_TEST_PASSWORD = "password-with-at-least-12-characters"  # noqa: S105
_DEFAULT_HASH = _compute_hash(DEFAULT_TEST_PASSWORD)


def random_user(
    fake: Faker = DEFAULT_FAKER, password: str | None = None, **overrides
) -> dict[str, Any]:
    assert set(overrides.keys()).issubset({c.name for c in users.columns})

    data = {
        "name": fake.user_name(),
        "email": fake.email().lower(),
        "password_hash": _DEFAULT_HASH,
        "status": UserStatus.ACTIVE,
    }

    assert set(data.keys()).issubset({c.name for c in users.columns})

    # transform password in hash
    if password:
        assert len(password) >= 12
        overrides["password_hash"] = _compute_hash(password)

    data.update(overrides)
    return data


def random_pre_registration_details(
    fake: Faker = DEFAULT_FAKER,
    *,
    user_id: int | None = None,
    created_by: int | None = None,
    **overrides,
):
    assert set(overrides.keys()).issubset(
        {c.name for c in users_pre_registration_details.columns}
    )

    data = {
        "user_id": user_id,
        "pre_first_name": fake.first_name(),
        "pre_last_name": fake.last_name(),
        "pre_email": fake.email(),
        "pre_phone": fake.phone_number(),
        "institution": fake.company(),
        "address": fake.address().replace("\n", ", "),
        "city": fake.city(),
        "state": fake.state(),
        "country": fake.country(),
        "postal_code": fake.postcode(),
        "extras": {
            "application": fake.word(),
            "description": fake.sentence(),
            "hear": fake.word(),
            "privacyPolicy": True,
            "eula": True,
            "ipinfo": {"x-real-ip": "127.0.0.1"},
        },
        "created_by": created_by,  # user id
    }

    assert set(data.keys()).issubset(
        {c.name for c in users_pre_registration_details.columns}
    )

    data.update(overrides)
    return data


def random_project(fake: Faker = DEFAULT_FAKER, **overrides) -> dict[str, Any]:
    """Generates random fake data projects DATABASE table"""
    data = {
        "uuid": fake.uuid4(),
        "name": fake.word(),
        "description": fake.sentence(),
        "prj_owner": fake.pyint(),
        "thumbnail": fake.image_url(width=120, height=120),
        "access_rights": {},
        "workbench": {},
        "published": False,
    }
    assert set(data.keys()).issubset({c.name for c in projects.columns})

    data.update(overrides)
    return data


def random_group(fake: Faker = DEFAULT_FAKER, **overrides) -> dict[str, Any]:

    data = {
        "name": fake.company(),
        "description": fake.text(),
        "type": GroupType.STANDARD.name,
    }

    assert set(data.keys()).issubset({c.name for c in groups.columns})  # nosec

    data.update(overrides)
    return data


def fake_pipeline(**overrides) -> dict[str, Any]:
    data = {
        "dag_adjacency_list": json.dumps({}),
        "state": random.choice(_STATES),
    }
    data.update(overrides)
    return data


def fake_task_factory(first_internal_id=1) -> Callable:
    # Each new instance of fake_task will get a copy
    _index_in_sequence = itertools.count(start=first_internal_id)

    def fake_task(**overrides) -> dict[str, Any]:
        t0 = datetime.utcnow()
        data = {
            "project_id": uuid4(),
            "node_id": uuid4(),
            "job_id": uuid4(),
            "internal_id": next(_index_in_sequence),
            "schema": json.dumps({}),
            "inputs": json.dumps({}),
            "outputs": json.dumps({}),
            "image": json.dumps({}),
            "state": random.choice(_STATES),
            "submit": t0,
            "start": t0 + timedelta(seconds=1),
            "end": t0 + timedelta(minutes=5),
        }

        data.update(overrides)
        return data

    return fake_task


def random_product(
    group_id: int | None = None,
    registration_email_template: str | None = None,
    fake: Faker = DEFAULT_FAKER,
    **overrides,
):
    """

    Foreign keys are:
        - group_id: product group ID. SEE get_or_create_product_group to produce `group_id`
        - registration_email_template
    """

    name = overrides.get("name")
    suffix = fake.unique.word() if name is None else name

    data = {
        "name": f"prd_{suffix}",
        "display_name": suffix.capitalize().replace("_", " "),
        "short_name": suffix[:4],
        "host_regex": r"[a-zA-Z0-9]+\.com",
        "support_email": f"support@{suffix}.io",
        "twilio_messaging_sid": fake.random_element(elements=(None, fake.uuid4()[:34])),
        "vendor": Vendor(
            name=fake.company(),
            copyright=fake.company_suffix(),
            url=fake.url(),
            license_url=fake.url(),
            invitation_url=fake.url(),
            has_landing_page=fake.boolean(),
            address=fake.address().replace("\n", ". "),
        ),
        "registration_email_template": registration_email_template,
        "created": fake.date_time_this_decade(),
        "modified": fake.date_time_this_decade(),
        "priority": fake.pyint(0, 10),
        "max_open_studies_per_user": fake.pyint(1, 10),
        "group_id": group_id,
    }

    assert set(data.keys()).issubset({c.name for c in products.columns})
    data.update(overrides)
    return data


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def random_payment_method(
    fake: Faker = DEFAULT_FAKER,
    **overrides,
) -> dict[str, Any]:
    from simcore_postgres_database.models.payments_methods import payments_methods

    data = {
        "payment_method_id": fake.uuid4(),
        "user_id": fake.pyint(),
        "wallet_id": fake.pyint(),
        "initiated_at": utcnow(),
        "state": InitPromptAckFlowState.PENDING,
        "completed_at": None,
    }
    # state is not added on purpose
    assert set(data.keys()).issubset({c.name for c in payments_methods.columns})

    data.update(overrides)
    return data


def random_payment_transaction(
    fake: Faker = DEFAULT_FAKER,
    **overrides,
) -> dict[str, Any]:
    """Generates Metadata + concept/info (excludes state)"""
    from simcore_postgres_database.models.payments_transactions import (
        payments_transactions,
    )

    # initiated
    data = {
        "payment_id": fake.uuid4(),
        "price_dollars": "123456.78",
        "osparc_credits": "123456.78",
        "product_name": "osparc",
        "user_id": fake.pyint(),
        "user_email": fake.email().lower(),
        "wallet_id": 1,
        "comment": "Free starting credits",
        "initiated_at": utcnow(),
        "state": PaymentTransactionState.PENDING,
        "completed_at": None,
    }
    # state is not added on purpose
    assert set(data.keys()).issubset({c.name for c in payments_transactions.columns})

    data.update(overrides)
    return data


def random_payment_autorecharge(
    primary_payment_method_id: str = DEFAULT_FAKER.uuid4(),
    fake: Faker = DEFAULT_FAKER,
    **overrides,
) -> dict[str, Any]:
    from simcore_postgres_database.models.payments_autorecharge import (
        payments_autorecharge,
    )

    data = {
        "wallet_id": fake.pyint(),
        "enabled": True,
        "primary_payment_method_id": primary_payment_method_id,
        "top_up_amount_in_usd": 100,
        "monthly_limit_in_usd": 1000,
    }
    assert set(data.keys()).issubset({c.name for c in payments_autorecharge.columns})

    data.update(overrides)
    return data


def random_api_key(
    product_name: str, user_id: int, fake: Faker = DEFAULT_FAKER, **overrides
) -> dict[str, Any]:
    data = {
        "display_name": fake.word(),
        "product_name": product_name,
        "user_id": user_id,
        "api_key": fake.password(),
        "api_secret": fake.password(),
        "expires_at": None,
    }
    assert set(data.keys()).issubset({c.name for c in api_keys.columns})  # nosec
    data.update(**overrides)
    return data


def random_payment_method_view(
    fake: Faker = DEFAULT_FAKER, **overrides
) -> dict[str, Any]:
    # Produces data for GetPaymentMethod
    data = {
        "id": fake.uuid4(),
        "card_holder_name": fake.name(),
        "card_number_masked": f"**** **** **** {fake.credit_card_number()[:4]}",
        "card_type": fake.credit_card_provider(),
        "expiration_month": fake.random_int(min=1, max=12),
        "expiration_year": fake.future_date().year,
        "created": utcnow(),
    }
    assert set(overrides.keys()).issubset(data.keys())
    data.update(**overrides)
    return data
