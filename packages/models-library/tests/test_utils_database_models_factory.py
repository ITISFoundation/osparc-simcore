# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from models_library.utils.database_models_factory import (
    convert_sa_table_to_pydantic_model,
)
from pydantic import BaseModel

# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import
from simcore_postgres_database.models import *

# pylint: enable=wildcard-import
# pylint: enable=unused-wildcard-import
from simcore_postgres_database.models.base import metadata
from simcore_postgres_database.models.projects_snapshots import projects_snapshots


@pytest.mark.parametrize("table_cls", metadata.tables.values(), ids=lambda t: t.name)
def test_table_to_pydantic_models(table_cls):

    PydanticOrm = convert_sa_table_to_pydantic_model(
        table=table_cls, include_server_defaults=True
    )
    assert issubclass(PydanticOrm, BaseModel)

    print(PydanticOrm.schema_json(indent=2))

    # TODO: create fakes automatically? SEE packages/pytest-simcore/src/pytest_simcore/helpers/rawdata_fakers.py
    # instance = PydanticModelAtDB.create_fake(**overrides)
    # assert issubclass(instance, PydanticModelAtDB)


def test_snapshot_pydantic_model(faker):
    Snapshot = convert_sa_table_to_pydantic_model(
        projects_snapshots, include_server_defaults=True
    )

    snapshot = Snapshot(
        id=0,
        name=faker.word(),
        created_at=faker.date_time(),
        parent_uuid=faker.uuid4(cast_to=None),
        project_uuid=faker.uuid4(),
    )
    assert snapshot.id == 0
