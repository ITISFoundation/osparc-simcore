# nopycln: file
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from models_library.utils.database_models_factory import (
    create_pydantic_model_from_sa_table,
)
from pydantic import BaseModel

# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import
from simcore_postgres_database.models import *

# pylint: enable=wildcard-import
# pylint: enable=unused-wildcard-import
from simcore_postgres_database.models.base import metadata


@pytest.mark.parametrize("table_cls", metadata.tables.values(), ids=lambda t: t.name)
def test_table_to_pydantic_models(table_cls):
    PydanticOrm = create_pydantic_model_from_sa_table(
        table=table_cls, include_server_defaults=True
    )
    assert issubclass(PydanticOrm, BaseModel)

    print(PydanticOrm.schema_json(indent=2))

    # TODO: create fakes automatically? SEE packages/pytest-simcore/src/pytest_simcore/helpers/rawdata_fakers.py
    # instance = PydanticModelAtDB.create_fake(**overrides)
    # assert issubclass(instance, PydanticModelAtDB)
