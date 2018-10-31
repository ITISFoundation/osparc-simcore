import datetime

import requests
import sqlalchemy as sa

from simcore_sdk.models.pipeline_models import (Base, ComputationalPipeline,
                                                ComputationalTask)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE = 'sidecar_test'
USER = 'scu'
PASS = 'scu'

ACCESS_KEY = '12345678'
SECRET_KEY = '12345678'

BUCKET_NAME ="simcore-testing"

RABBIT_USER = "rabbit"
RABBIT_PWD = "carrot"

def is_responsive(url, code=200):
    """Check if something responds to ``url`` syncronously"""
    try:
        response = requests.get(url)
        if response.status_code == code:
            return True
    except requests.exceptions.RequestException as _e:
        pass

    return False

def is_postgres_responsive(url):
    """Check if something responds to ``url`` """
    try:
        engine = sa.create_engine(url)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:
        return False
    return True

def create_tables(url, engine=None):
    if not engine:
        engine = create_engine(url,
            client_encoding="utf8",
            connect_args={"connect_timeout": 30},
                pool_pre_ping=True)

    Base.metadata.create_all(engine)

def drop_tables(url, engine=None):
    if not engine:
        engine = create_engine(url,
            client_encoding="utf8",
            connect_args={"connect_timeout": 30},
                pool_pre_ping=True)

    Base.metadata.drop_tables(engine)

def setup_sleepers(url):
    db_engine = create_engine(url,
        client_encoding="utf8",
        connect_args={"connect_timeout": 30},
        pool_pre_ping=True)

    DatabaseSession = sessionmaker(db_engine)
    db_session = DatabaseSession()


    dag_adjacency_list = {"e609a68c-d743-4a12-9745-f31734d1b911": ["3e5103b3-8930-4025-846b-b8995460379e"], "3e5103b3-8930-4025-846b-b8995460379e": []}

    pipeline = ComputationalPipeline(dag_adjacency_list=dag_adjacency_list, state=0)
    db_session.add(pipeline)
    db_session.flush()
    pipeline_id = pipeline.pipeline_id

    task_id_1 = 820
    node_id_1 = "e609a68c-d743-4a12-9745-f31734d1b911"
    job_id_1 = "79da6b3a-d832-4ec0-b484-fc13e7a11af2"
    internal_id_1 = 1

    node_inputs_1 = [{"key": "in_1", "label": "Number of seconds to sleep", "desc": "Number of seconds to sleep", "type": "file-url", "value": "null"}, {"key": "in_2", "label": "Number of seconds to sleep", "desc": "Number of seconds to sleep", "type": "integer", "value": 4}]
    node_outputs_1 = [{"key": "out_1", "label": "Number of seconds to sleep", "desc": "Number of seconds to sleep", "type": "file-url", "value": "null"}, {"key": "out_2", "label": "Number of seconds to sleep", "desc": "Number of seconds to sleep", "type": "integer", "value": 1}]

    node_key = "simcore/services/comp/itis/sleeper"
    node_version = "0.0.1"
    # create the task
    task_1 = {
        "input":node_inputs_1,
        "output":node_outputs_1,
        "image":{
            "name":node_key,
            "tag":node_version
        }
    }

    comp_task_1 = ComputationalTask(
        pipeline_id=pipeline_id,
        node_id=node_id_1,
        internal_id=internal_id_1,
        image=task_1["image"],
        input=task_1["input"],
        output=task_1["output"],
        submit=datetime.datetime.utcnow()
        )


    db_session.add(comp_task_1)
    db_session.commit()


    task_id_2 = 821
    node_id_2 = "3e5103b3-8930-4025-846b-b8995460379e"
    job_id_2 = "1c68fcb2-806a-40cb-a223-1c282279e51b"
    internal_id_2 = 2

    node_inputs_2 = [{"key": "in_1", "label": "Number of seconds to sleep", "desc": "Number of seconds to sleep", "type": "file-url", "value": "link.e609a68c-d743-4a12-9745-f31734d1b911.out_1"}, {"key": "in_2", "label": "Number of seconds to sleep", "desc": "Number of seconds to sleep", "type": "integer", "value": "link.e609a68c-d743-4a12-9745-f31734d1b911.out_2"}]
    node_outputs_2 = [{"key": "out_1", "label": "Number of seconds to sleep", "desc": "Number of seconds to sleep", "type": "file-url", "value": "null"}, {"key": "out_2", "label": "Number of seconds to sleep", "desc": "Number of seconds to sleep", "type": "integer", "value": 5}]

    node_key = "simcore/services/comp/itis/sleeper"
    node_version = "0.0.1"
    # create the task
    task_2 = {
        "input":node_inputs_2,
        "output":node_outputs_2,
        "image":{
            "name":node_key,
            "tag":node_version
        }
    }

    comp_task_2 = ComputationalTask(
        pipeline_id=pipeline_id,
        node_id=node_id_2,
        internal_id=internal_id_2,
        image=task_2["image"],
        input=task_2["input"],
        output=task_2["output"],
        submit=datetime.datetime.utcnow()
        )


    db_session.add(comp_task_2)
    db_session.commit()

    return pipeline_id
