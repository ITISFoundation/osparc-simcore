# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import json

import pytest

from simcore_service_catalog.db import tables
from simcore_service_catalog.models.domain.dag import DAG, DAGAtDB
from simcore_service_catalog.models.schemas.dag import DAGIn, DAGOut

# from typing import Optional, TypeVar, Generic
# from pydantic import GenericModel, BaseModel

# DataT = TypeVar('DataT')

# class Error(BaseModel):
#     code: int
#     message: str

# class Envelope(GenericModel, Generic[DataT]):
#     data: Optional[DataT]
#     error: Optional[Error]


@pytest.mark.skip(reason="DEV")
def test_dev():

    dag_in = DAGIn(
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


def test_api_in_2_orm(fake_data_dag_in):
    # dag in to db
    dag_in = DAGIn(**fake_data_dag_in)

    # TODO: create DAG.from_api( :DAGIn)
    # SEE crud_dags.create_dag
    selection = set(tables.dags.columns.keys()).remove("workbench")
    dag_orm = DAG(
        id=1,
        workbench=json.dumps(fake_data_dag_in["workbench"]),
        **dag_in.dict(include=selection, exclude={"workbench"}),
    )


def test_orm_2_api_out(fake_data_dag_in):
    dag_orm = DAG(
        id=1,
        key="simcore/services/comp/foo",
        version="1.0.0",
        name="bar",
        description="some",
        contact="me@me.com",
        workbench=json.dumps(fake_data_dag_in["workbench"]),
    )

    dag_db = DAGAtDB.from_orm(dag_orm)
    assert type(dag_db.workbench) == dict

    dag_out = DAGOut(**dag_db.dict())
    assert dag_out.id == 1
