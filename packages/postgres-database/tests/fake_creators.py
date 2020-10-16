import itertools
import json
import random
from datetime import datetime, timedelta
from typing import Dict
from uuid import uuid4

import faker

from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.webserver_models import ProjectType, UserStatus

STATES = [StateType.NOT_STARTED, StateType.PENDING, StateType.RUNNING, StateType.SUCCESS, StateType.FAILED]


_index_in_sequence = itertools.count(start=1)
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
    data = dict(
        name=fake.company(), description=fake.text(), type=ProjectType.STANDARD.name
    )
    data.update(overrides)
    return data


def fake_pipeline(**overrides) -> Dict:
    data = dict(dag_adjacency_list=json.dumps({}), state=random.choice(STATES),)
    data.update(overrides)
    return data


def fake_task(**overrides) -> Dict:
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
