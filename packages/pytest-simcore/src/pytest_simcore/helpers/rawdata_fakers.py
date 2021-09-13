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
from simcore_postgres_database.webserver_models import ProjectType, UserStatus

STATES = [
    StateType.NOT_STARTED,
    StateType.PENDING,
    StateType.RUNNING,
    StateType.SUCCESS,
    StateType.FAILED,
]


fake = faker.Faker()


def random_user(**overrides) -> Dict[str, Any]:
    data = dict(
        name=fake.name(),
        email=fake.email(),
        password_hash=fake.numerify(text="#" * 5),
        status=UserStatus.ACTIVE,
        created_ip=fake.ipv4(),
    )
    data.update(overrides)
    return data


def random_project(**overrides) -> Dict[str, Any]:
    """Generates random fake data projects DATABASE table"""
    data = dict(
        uuid=fake.uuid4(),
        name=fake.word(),
        description=fake.sentence(),
        prj_owner=fake.pyint(),
        thumbnail=fake.image_url(width=120, height=120),
        access_rights={},
        workbench={},
        published=False,
    )
    data.update(overrides)
    return data


def random_group(**overrides) -> Dict[str, Any]:
    data = dict(
        name=fake.company(), description=fake.text(), type=ProjectType.STANDARD.name
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
