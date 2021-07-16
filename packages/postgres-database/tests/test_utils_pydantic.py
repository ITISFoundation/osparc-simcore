import pytest
from pydantic import BaseModel
from simcore_postgres_database.models import *
from simcore_postgres_database.models.base import metadata
from simcore_postgres_database.utils_pydantic import sa_table_to_pydantic_model


@pytest.mark.parametrized("table_cls", metadata.tables)
def test_table_to_pydantic_models(table_cls):

    PydanticModelAtDB = sa_table_to_pydantic_model(table=table_cls, exclude={})
    assert issubclass(PydanticModelAtDB, BaseModel)
    print(PydanticModelAtDB.schema_json(indent=2))

    # TODO: create fakes automatically?
