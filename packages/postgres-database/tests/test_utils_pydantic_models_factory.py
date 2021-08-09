from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import BaseModel

# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import
from simcore_postgres_database.models import *

# pylint: enable=wildcard-import
# pylint: enable=unused-wildcard-import
from simcore_postgres_database.models.base import metadata
from simcore_postgres_database.models.snapshots import snapshots
from simcore_postgres_database.utils_pydantic_models_factory import (
    sa_table_to_pydantic_model,
)


@pytest.mark.parametrize("table_cls", metadata.tables.values(), ids=lambda t: t.name)
def test_table_to_pydantic_models(table_cls):

    PydanticModelAtDB = sa_table_to_pydantic_model(table=table_cls)
    assert issubclass(PydanticModelAtDB, BaseModel)
    print(PydanticModelAtDB.schema_json(indent=2))

    # TODO: create fakes automatically?


def test_snapshot_pydantic_model():
    Snapshot = sa_table_to_pydantic_model(snapshots)

    snapshot = Snapshot(
        id=0,
        name="foo",
        created_at=datetime.now(),
        parent_uuid=uuid4(),
        child_index=2,
        project_uuid=uuid4(),
    )
    assert snapshot.id == 0
