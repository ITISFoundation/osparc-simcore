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
from datetime import datetime, timedelta
from typing import Any, Callable, Dict
from uuid import uuid4

import faker
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users
from simcore_postgres_database.webserver_models import ProjectType, UserStatus

STATES = [
    StateType.NOT_STARTED,
    StateType.PENDING,
    StateType.RUNNING,
    StateType.SUCCESS,
    StateType.FAILED,
]


_faker = faker.Faker()


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


def random_user(**overrides) -> Dict[str, Any]:
    data = dict(
        name=_faker.name(),
        email=_faker.email(),
        password_hash=_DEFAULT_HASH,
        status=UserStatus.ACTIVE,
        created_ip=_faker.ipv4(),
    )
    assert set(data.keys()).issubset(set(c.name for c in users.columns))  # nosec

    # transform password in hash
    password = overrides.pop("password", None)
    if password:
        overrides["password_hash"] = _compute_hash(password)

    data.update(overrides)
    return data


def random_project(**overrides) -> Dict[str, Any]:
    """Generates random fake data projects DATABASE table"""
    data = dict(
        uuid=_faker.uuid4(),
        name=_faker.word(),
        description=_faker.sentence(),
        prj_owner=_faker.pyint(),
        thumbnail=_faker.image_url(width=120, height=120),
        access_rights={},
        workbench={},
        published=False,
    )
    assert set(data.keys()).issubset(set(c.name for c in projects.columns))  # nosec

    data.update(overrides)
    return data


def random_group(**overrides) -> Dict[str, Any]:
    data = dict(
        name=_faker.company(), description=_faker.text(), type=ProjectType.STANDARD.name
    )
    data.update(overrides)
    return data


def fake_pipeline(**overrides) -> Dict[str, Any]:
    data = dict(
        dag_adjacency_list=json.dumps({}),
        state=random.choice(STATES),
    )
    data.update(overrides)
    return data


def fake_task_factory(first_internal_id=1) -> Callable:
    # Each new instance of fake_task will get a copy
    _index_in_sequence = itertools.count(start=first_internal_id)

    def fake_task(**overrides) -> Dict[str, Any]:

        t0 = datetime.utcnow()
        data = dict(
            project_id=uuid4(),
            node_id=uuid4(),
            job_id=uuid4(),
            internal_id=next(_index_in_sequence),
            schema=json.dumps({}),
            inputs=json.dumps({}),
            outputs=json.dumps({}),
            image=json.dumps({}),
            state=random.choice(STATES),
            submit=t0,
            start=t0 + timedelta(seconds=1),
            end=t0 + timedelta(minutes=5),
        )

        data.update(overrides)
        return data

    return fake_task
