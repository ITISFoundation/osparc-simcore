import logging
import os
import sys
from pathlib import Path

import pandas
import requests
import sqlalchemy as sa
from simcore_service_storage.models import (
    FileMetaData,
    file_meta_data,
    groups,
    projects,
    user_to_groups,
    users,
)

log = logging.getLogger(__name__)


DATABASE = "test"
USER = "admin"
PASS = "admin"

ACCESS_KEY = "12345678"
SECRET_KEY = "12345678"

BUCKET_NAME = "simcore-testing-bucket"
USER_ID = "0"

PG_TABLES_NEEDED_FOR_STORAGE = [
    user_to_groups,
    file_meta_data,
    projects,
    users,
    groups,
]

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
DATA_DIR = CURRENT_DIR / "data"


def has_datcore_tokens() -> bool:
    # TODO: activate tests against BF services in the CI.
    #
    # CI shall add BF_API_KEY, BF_API_SECRET environs as secrets
    #
    if not os.environ.get("BF_API_KEY") or not os.environ.get("BF_API_SECRET"):
        return False
    return True


def is_responsive(url, code=200) -> bool:
    """Check if something responds to ``url`` syncronously"""
    try:
        response = requests.get(url)
        if response.status_code == code:
            return True
    except requests.exceptions.RequestException as _e:
        pass

    return False


def insert_metadata(url: str, fmd: FileMetaData):
    # FIXME: E1120:No value for argument 'dml' in method call
    # pylint: disable=E1120
    ins = file_meta_data.insert().values(
        file_uuid=fmd.file_uuid,
        location_id=fmd.location_id,
        location=fmd.location,
        bucket_name=fmd.bucket_name,
        object_name=fmd.object_name,
        project_id=fmd.project_id,
        project_name=fmd.project_name,
        node_id=fmd.node_id,
        node_name=fmd.node_name,
        file_name=fmd.file_name,
        user_id=fmd.user_id,
        user_name=fmd.user_name,
        file_id=fmd.file_id,
        raw_file_path=fmd.raw_file_path,
        display_file_path=fmd.display_file_path,
        created_at=fmd.created_at,
        last_modified=fmd.last_modified,
        file_size=fmd.file_size,
        entity_tag=fmd.entity_tag,
    )

    engine = sa.create_engine(url)
    try:
        conn = engine.connect()
        conn.execute(ins)
    finally:
        engine.dispose()


def fill_tables_from_csv_files(url):
    engine = None

    try:
        engine = sa.create_engine(url)
        for table in ["users", "file_meta_data", "projects"]:
            with open(DATA_DIR / f"{table}.csv", "r") as file:
                data_df = pandas.read_csv(file)
                data_df.to_sql(
                    table, con=engine, index=False, index_label="id", if_exists="append"
                )
    finally:
        if engine is not None:
            engine.dispose()
