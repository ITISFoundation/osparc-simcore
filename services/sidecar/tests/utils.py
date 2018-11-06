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
    project_id = pipeline.project_id

    node_id_1 = "e609a68c-d743-4a12-9745-f31734d1b911"
    internal_id_1 = 1

    node_schema = {
        "inputs":{
            "in_1":{
                "label": "Number of seconds to sleep", 
                "description": "Number of seconds to sleep", 
                "displayOrder":0,
                "type": "data:*/*"
            },
            "in_2": {
                "label": "Number of seconds to sleep", 
                "description": "Number of seconds to sleep", 
                "displayOrder":1,
                "type": "integer", 
                "defaultValue": 4
            }
        },
        "outputs":{
            "out_1":{
                "label": "Number of seconds to sleep", 
                "description": "Number of seconds to sleep", 
                "displayOrder":0,
                "type": "data:*/*"
            },
            "out_2": {
                "label": "Number of seconds to sleep", 
                "description": "Number of seconds to sleep", 
                "displayOrder":1,
                "type": "integer"
            }
        }
    }
    node_inputs_1 = {}
    node_outputs_1 = {"out_2":1}

    node_key = "simcore/services/comp/itis/sleeper"
    node_version = "0.0.1"
    # create the task
    comp_task_1 = ComputationalTask(
        project_id=project_id,
        node_id=node_id_1,
        internal_id=internal_id_1,
        schema=node_schema,
        image={"name":node_key, "tag":node_version},
        inputs=node_inputs_1,
        outputs=node_outputs_1,
        submit=datetime.datetime.utcnow()
        )
    db_session.add(comp_task_1)
    db_session.commit()

    node_id_2 = "3e5103b3-8930-4025-846b-b8995460379e"
    internal_id_2 = 2

    node_inputs_2 = {"in_1":{"nodeUuid": "e609a68c-d743-4a12-9745-f31734d1b911", "output":"out_1"}, "in_2":{"nodeUuid": "e609a68c-d743-4a12-9745-f31734d1b911", "output":"out_2"}}
    node_outputs_2 = {"out_2":5}

    node_key = "simcore/services/comp/itis/sleeper"
    node_version = "0.0.1"
    # create the task
    comp_task_2 = ComputationalTask(
        project_id=project_id,
        node_id=node_id_2,
        internal_id=internal_id_2,
        schema=node_schema,
        image={"name":node_key, "tag":node_version},
        inputs=node_inputs_2,
        outputs=node_outputs_2,
        submit=datetime.datetime.utcnow()
        )

    db_session.add(comp_task_2)
    db_session.commit()

    return project_id
