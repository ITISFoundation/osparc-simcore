import pytest
# pylint:disable=unused-import
from pytest_docker import docker_ip, docker_services
from sqlalchemy import JSON, Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

# pylint:disable=redefined-outer-name


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
