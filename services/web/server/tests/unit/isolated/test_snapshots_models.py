# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime
from uuid import uuid4

from faker import Faker
from models_library.utils.database_models_factory import sa_table_to_pydantic_model
from simcore_postgres_database.models.snapshots import snapshots
from simcore_service_webserver.snapshots_models import Snapshot

SnapshotORM = sa_table_to_pydantic_model(snapshots)


def test_snapshot_orm_to_domain_model(faker: Faker):

    snapshot_orm = SnapshotORM(
        id=faker.random_int(min=0),
        name=faker.name(),
        created_at=faker.date_time(),
        parent_uuid=faker.uuid4(),
        project_uuid=faker.uuid4(),
    )

    # snapshot_orm is dot-attr accessed so
    snapshot = Snapshot.from_orm(snapshot_orm)

    assert snapshot.dict(by_alias=True) == snapshot_orm.dict()

    # snapshot_orm here is dict-like so ...
    assert Snapshot.parse_obj(snapshot_orm) == snapshot


def test_compose_project_uuid():

    prj_id1 = Snapshot.compose_project_uuid(uuid4(), datetime.now())
    assert prj_id1

    prj_id2 = Snapshot.compose_project_uuid(str(uuid4()), datetime.now())
    assert prj_id2
