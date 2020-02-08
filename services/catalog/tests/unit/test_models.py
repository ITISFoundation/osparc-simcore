# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pydantic import BaseModel, validator

from fakes import DAG_WORKBENCH_DICT, DAG_WORKBENCH_JSON
from simcore_service_catalog.orm import orm_dags
from simcore_service_catalog.schemas import schemas_dags


class User(BaseModel):
    id: int
    name = 'Jane'

class UserDetailed(User):
    surname = 'Doe'



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

    dag_in = schemas_dags.DAGIn(key="simcore/services/frontend/nodes-group/macros/")

    assert 'key' in dag_in.__fields_set__
    assert 'version' not in dag_in.__fields_set__

    print()
    # to update_dat
    print(dag_in.dict(exclude_unset=True))

    # to set or create dat
    print(dag_in.dict())
    print(dag_in.dict(exclude_none=True))






def test_db_to_api():

    assert type(DAG_WORKBENCH_JSON) == str

    dag_orm = orm_dags.DAG(id=1, key="foo", version="1.0.0", name="bar",
        description="some", contact="me", workbench=DAG_WORKBENCH_JSON)

    dag_db = schemas_dags.DAGAtDB.from_orm(dag_orm)

    assert type(dag_db.workbench) == dict

    dag_out = schemas_dags.DAGOut(**dag_db.dict())
