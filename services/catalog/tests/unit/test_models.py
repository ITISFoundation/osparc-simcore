# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json

from pydantic import BaseModel, validator

from simcore_service_catalog.orm import DAG
from simcore_service_catalog.schemas import schemas_dags


class User(BaseModel):
    id: int
    name = "Jane"


class UserDetailed(User):
    surname = "Doe"


# from typing import Optional, TypeVar, Generic
# from pydantic import GenericModel, BaseModel

# DataT = TypeVar('DataT')

# class Error(BaseModel):
#     code: int
#     message: str


# class Envelope(GenericModel, Generic[DataT]):
#     data: Optional[DataT]
#     error: Optional[Error]


def test_dev():

    dag_in = schemas_dags.DAGIn(
        key="simcore/services/frontend/nodes-group/macros/", version="1.0.0", name="foo"
    )

    assert "key" in dag_in.__fields_set__
    assert "version" in dag_in.__fields_set__
    assert "description" not in dag_in.__fields_set__

    print()
    # to update_dat
    print(dag_in.dict(exclude_unset=True))

    # to set or create dat
    print(dag_in.dict())
    print(dag_in.dict(exclude_none=True))


def test_db_to_api(fake_data_dag_in):
    dag_orm = DAG(
        id=1,
        key="simcore/services/comp/foo",
        version="1.0.0",
        name="bar",
        description="some",
        contact="me@me.com",
        workbench=json.dumps(fake_data_dag_in["workbench"]),
    )

    dag_db = schemas_dags.DAGAtDB.from_orm(dag_orm)

    assert type(dag_db.workbench) == dict

    dag_out = schemas_dags.DAGOut(**dag_db.dict())
