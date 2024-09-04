# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from simcore_postgres_database.models.workspaces import workspaces


@pytest.fixture
def workspaces_clean_db(postgres_db: sa.engine.Engine) -> Iterator[None]:
    with postgres_db.connect() as con:
        yield
        con.execute(workspaces.delete())
