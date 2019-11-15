# pylint:disable=redefined-outer-name
# pylint:disable=unused-import

import pytest
# FIXME: Not sure why but if this import is removed pytest_docker
# gets the docker_compose_file wrong in tests_nodes.
#  Somehow the fixture in packages/simcore-sdk/tests/node_ports/conftest.py
# does not override override of docker_compose_file from pytest_docker!
from pytest_docker import docker_ip, docker_services
from simcore_sdk.models.pipeline_models import (ComputationalPipeline,
                                                ComputationalTask,
                                                comp_pipeline, comp_tasks)
from sqlalchemy import JSON, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.attributes import flag_modified

BASE = declarative_base()
class User(BASE):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    data = Column(JSON)


@pytest.mark.enable_travis
def test_alchemy(engine, session):
    BASE.metadata.create_all(engine)
    users = ['alpha', 'beta', 'gamma']

    for u in users:
        data = {}
        data['counter'] = 0
        user = User(name=u, data=data)
        session.add(user)
        session.commit()

    users2 = session.query(User).all()
    assert len(users2) == len(users)

    alpha = session.query(User).filter(User.name == 'alpha').one()

    assert alpha

    assert alpha.data['counter'] == 0
    alpha.data['counter'] = 42
    flag_modified(alpha, "data")
    session.commit()

    alpha2 = session.query(User).filter(User.name == 'alpha').one()
    assert alpha2.data['counter'] == 42


def test_legacy_queries_with_mapper_adapter():
    """Checks to ensure that LEGACY queries still work with
        mapper adapter

        This test was added to ensure we could `disable no-member`
        for ComputationalTask and ComputationalPipeline mapped classes
    """
    column_type = type(User.name)
    # pylint: disable=no-member

    assert hasattr(ComputationalTask, "node_id")
    assert hasattr(ComputationalTask, "project_id")
    assert isinstance(ComputationalTask.node_id, column_type)
    assert isinstance(ComputationalTask.project_id, column_type)

    assert hasattr(ComputationalTask, "schema")
    assert hasattr(ComputationalTask, "inputs")
    assert hasattr(ComputationalTask, "outputs")
    assert isinstance(ComputationalTask.schema, column_type)
    assert isinstance(ComputationalTask.inputs, column_type)
    assert isinstance(ComputationalTask.outputs, column_type)

    assert hasattr(ComputationalPipeline, "project_id")
    assert isinstance(ComputationalPipeline.project_id, column_type)

    # pylint: disable=protected-access
    column_names = set(c.name for c in comp_pipeline.c)
    assert set(ComputationalPipeline._sa_class_manager.keys()) == column_names

    column_names = set(c.name for c in comp_tasks.c)
    assert set(ComputationalTask._sa_class_manager.keys()) == column_names
