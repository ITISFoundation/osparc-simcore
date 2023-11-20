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
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users
from simcore_postgres_database.webserver_models import GroupType, UserStatus

STATES = [
    StateType.NOT_STARTED,
    StateType.PENDING,
    StateType.RUNNING,
    StateType.SUCCESS,
    StateType.FAILED,
]


FAKE: Final = faker.Faker()


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


_DEFAULT_HASH = _compute_hash("secret")


def random_user(**overrides) -> dict[str, Any]:
    data = {
        "name": FAKE.user_name(),
        "email": FAKE.email().lower(),
        "password_hash": _DEFAULT_HASH,
        "status": UserStatus.ACTIVE,
    }
    assert set(data.keys()).issubset({c.name for c in users.columns})  # nosec

    # transform password in hash
    password = overrides.pop("password", None)
    if password:
        overrides["password_hash"] = _compute_hash(password)

    data.update(overrides)
    return data


def random_project(**overrides) -> dict[str, Any]:
    """Generates random fake data projects DATABASE table"""
    data = {
        "uuid": FAKE.uuid4(),
        "name": FAKE.word(),
        "description": FAKE.sentence(),
        "prj_owner": FAKE.pyint(),
        "thumbnail": FAKE.image_url(width=120, height=120),
        "access_rights": {},
        "workbench": {},
        "published": False,
    }
    assert set(data.keys()).issubset({c.name for c in projects.columns})  # nosec

    data.update(overrides)
    return data


def random_group(**overrides) -> dict[str, Any]:
    data = {
        "name": FAKE.company(),
        "description": FAKE.text(),
        "type": GroupType.STANDARD.name,
    }
    data.update(overrides)
    return data


def fake_pipeline(**overrides) -> dict[str, Any]:
    data = {
        "dag_adjacency_list": json.dumps({}),
        "state": random.choice(STATES),
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
            "state": random.choice(STATES),
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
    fake: Faker = FAKE,
    **overrides,
):
    """

    Foreign keys are:
        - group_id: product group ID. SEE get_or_create_product_group to produce `group_id`
        - registration_email_template
    """

    fake_vendor = {
        "name": fake.company(),
        "copyright": fake.company_suffix(),
        "url": fake.url(),
        "license_url": fake.url(),
        "invitation_url": fake.url(),
        "has_landing_page": fake.boolean(),
    }

    data = {
        "name": fake.unique.first_name(),
        "display_name": fake.company(),
        "short_name": fake.user_name()[:10],
        "host_regex": r"[a-zA-Z0-9]+\.com",
        "support_email": fake.email(),
        "twilio_messaging_sid": fake.random_element(elements=(None, fake.uuid4()[:34])),
        "vendor": fake.random_element([None, fake_vendor]),
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
    **overrides,
) -> dict[str, Any]:
    from simcore_postgres_database.models.payments_methods import payments_methods

    data = {
        "payment_method_id": FAKE.uuid4(),
        "user_id": FAKE.pyint(),
        "wallet_id": FAKE.pyint(),
        "initiated_at": utcnow(),
        "state": InitPromptAckFlowState.PENDING,
        "completed_at": None,
    }
    # state is not added on purpose
    assert set(data.keys()).issubset({c.name for c in payments_methods.columns})

    data.update(overrides)
    return data


def random_payment_transaction(
    **overrides,
) -> dict[str, Any]:
    """Generates Metadata + concept/info (excludes state)"""
    from simcore_postgres_database.models.payments_transactions import (
        payments_transactions,
    )

    # initiated
    data = {
        "payment_id": FAKE.uuid4(),
        "price_dollars": "123456.78",
        "osparc_credits": "123456.78",
        "product_name": "osparc",
        "user_id": FAKE.pyint(),
        "user_email": FAKE.email().lower(),
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
    primary_payment_method_id: str = FAKE.uuid4(),
    **overrides,
) -> dict[str, Any]:
    from simcore_postgres_database.models.payments_autorecharge import (
        payments_autorecharge,
    )

    data = {
        "wallet_id": FAKE.pyint(),
        "enabled": True,
        "primary_payment_method_id": primary_payment_method_id,
        "top_up_amount_in_usd": 100,
        "monthly_limit_in_usd": 1000,
    }
    assert set(data.keys()).issubset({c.name for c in payments_autorecharge.columns})

    data.update(overrides)
    return data


def random_api_key(product_name: str, user_id: int, **overrides) -> dict[str, Any]:
    data = {
        "display_name": FAKE.word(),
        "product_name": product_name,
        "user_id": user_id,
        "api_key": FAKE.password(),
        "api_secret": FAKE.password(),
        "expires_at": None,
    }
    assert set(data.keys()).issubset({c.name for c in api_keys.columns})  # nosec
    data.update(**overrides)
    return data


def random_payment_method_data(**overrides) -> dict[str, Any]:
    # Produces data for GetPaymentMethod
    data = {
        "id": FAKE.uuid4(),
        "card_holder_name": FAKE.name(),
        "card_number_masked": f"**** **** **** {FAKE.credit_card_number()[:4]}",
        "card_type": FAKE.credit_card_provider(),
        "expiration_month": FAKE.random_int(min=1, max=12),
        "expiration_year": FAKE.future_date().year,
        "created": utcnow(),
    }
    assert set(overrides.keys()).issubset(data.keys())
    data.update(**overrides)
    return data
