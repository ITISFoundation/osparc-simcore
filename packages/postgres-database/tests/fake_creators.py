import json
import random
from datetime import datetime, timedelta
from typing import Dict
from uuid import uuid4

import faker

from simcore_postgres_database.models.comp_pipeline import (
    FAILED,
    PENDING,
    RUNNING,
    SUCCESS,
    UNKNOWN,
)
from simcore_postgres_database.webserver_models import ProjectType, UserStatus

STATES = [UNKNOWN, PENDING, RUNNING, SUCCESS, FAILED]


fake = faker.Faker()


def random_user(**overrides):
    data = dict(
        name=fake.name(),
        email=fake.email(),
        password_hash=fake.numerify(text="#" * 5),
        status=UserStatus.ACTIVE,
        created_ip=fake.ipv4(),
    )
    data.update(overrides)
    return data


def random_project(**overrides):
    data = dict(
        uuid=uuid4(),
        name=fake.word(),
        description=fake.sentence(),
        prj_owner=fake.pyint(),
        access_rights={},
        workbench={},
        published=False,
    )
    data.update(overrides)
    return data


def random_group(**overrides):
    data = dict(name=fake.company(), description=fake.text(), type="STANDARD")
    data.update(overrides)
    return data


def fake_pipeline(**overrides) -> Dict:
    data = dict(dag_adjacency_list=json.dumps({}), state=random.choice(STATES),)
    data.update(overrides)
    return data


def fake_task(**overrides) -> Dict:
    data = dict(
        project_id=uuid4(),
        node_id=uuid4(),
        job_id=uuid4(),
        internal_id=1,  # TODO: incremental
        schema=json.dumps({}),
        inputs=json.dumps({}),
        outputs=json.dumps({}),
        image=json.dumps({}),
        state=random.choice(STATES),
        submit=datetime.utcnow(),
        start=datetime.utcnow(),
        end=datetime.utcnow(),
    )
    # TODO: state and times must be logic submit < start and end
    data.update(overrides)
    return data

