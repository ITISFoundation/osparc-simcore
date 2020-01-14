import logging
import os
import sys
from pathlib import Path

import pandas as pd
import pytest
import requests
import sqlalchemy as sa

from simcore_service_storage.models import (FileMetaData, file_meta_data,
                                            projects, user_to_projects, users)

log = logging.getLogger(__name__)


DATABASE = 'aio_login_tests'
USER = 'admin'
PASS = 'admin'

ACCESS_KEY = '12345678'
SECRET_KEY = '12345678'

BUCKET_NAME ="simcore-testing"
USER_ID = '0'

def current_dir():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

def data_dir():
    return current_dir() / Path("data")

def has_datcore_tokens()->bool:
    token = os.environ.get("BF_API_KEY", "none")
    if token == "none":
        pytest.skip("Datcore access tokens not available, skipping test")
        return False
    return True

def is_responsive(url, code=200):
    """Check if something responds to ``url`` syncronously"""
    try:
        response = requests.get(url)
        if response.status_code == code:
            return True
    except requests.exceptions.RequestException as _e:
        pass

    return False

def is_postgres_responsive(url):
    """Check if something responds to ``url`` """
    try:
        engine = sa.create_engine(url)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:
        return False
    return True

def create_tables(url, engine=None):
    meta = sa.MetaData()
    if not engine:
        engine = sa.create_engine(url)

    meta.drop_all(bind=engine, tables=[file_meta_data])
    meta.create_all(bind=engine, tables=[file_meta_data])


def drop_tables(url, engine=None):
    meta = sa.MetaData()
    if not engine:
        engine = sa.create_engine(url)

    meta.drop_all(bind=engine, tables=[file_meta_data])

def insert_metadata(url: str, fmd: FileMetaData):
    #FIXME: E1120:No value for argument 'dml' in method call
    # pylint: disable=E1120
    ins = file_meta_data.insert().values(
        file_uuid = fmd.file_uuid,
        location_id = fmd.location_id,
        location = fmd.location,
        bucket_name = fmd.bucket_name,
        object_name = fmd.object_name,
        project_id = fmd.project_id,
        project_name = fmd.project_name,
        node_id = fmd.node_id,
        node_name = fmd.node_name,
        file_name = fmd.file_name,
        user_id = fmd.user_id,
        user_name= fmd.user_name,
        file_id = fmd.file_id,
        raw_file_path = fmd.raw_file_path,
        display_file_path = fmd.display_file_path,
        created_at = fmd.created_at,
        last_modified = fmd.last_modified,
        file_size = fmd.file_size)


    engine = sa.create_engine(url)
    conn = engine.connect()
    conn.execute(ins)
    engine.dispose()

def create_full_tables(url):
    meta = sa.MetaData()
    engine = sa.create_engine(url)

    meta.drop_all(bind=engine, tables=[file_meta_data, projects, user_to_projects, users])
    meta.create_all(bind=engine, tables=[file_meta_data, projects, user_to_projects, users])

    for t in ["file_meta_data", "projects", "users", "user_to_projects"]:
        filename = t + ".csv"
        csv_file = str(data_dir() / Path(filename))
        with open(csv_file, 'r') as file:
            data_df = pd.read_csv(file)
            data_df.to_sql(t, con=engine, index=False, index_label="id", if_exists='append')

    # Leave here as a reference
    # import psycopg2
    # conn = psycopg2.connect(url)
    # cur = conn.cursor()
    # columns = [["file_uuid","location_id","location","bucket_name","object_name","project_id","project_name","node_id","node_name","file_name","user_id","user_name"],[],[],[]]
    # if False:
    #     for t in ["file_meta_data", "projects", "users", "user_to_projects"]:
    #         filename = t + ".sql"
    #         sqlfile = str(data_dir() / Path(filename))
    #         cur.execute(open(sqlfile, "r").read())
    # else:
    #     for t in ["file_meta_data", "projects", "users", "user_to_projects"]:
    #         filename = t + ".csv"
    #         csv_file = str(data_dir() / Path(filename))
    #         if False:
    #             with open(csv_file, 'r') as file:
    #                 next(file)
    #                 if t == "file_meta_data":
    #                     cur.copy_from(file, t, sep=',', columns=columns[0])
    #                 else:
    #                     cur.copy_from(file, t, sep=',')
    #                 conn.commit()
    #         else:
    #             with open(csv_file, 'r') as file:
    #                 data_df = pd.read_csv(file)
    #                 data_df.to_sql(t, con=engine, index=False, index_label="id", if_exists='append')
    engine.dispose()

def drop_all_tables(url):
    meta = sa.MetaData()
    engine = sa.create_engine(url)

    meta.drop_all(bind=engine, tables=[file_meta_data, projects, user_to_projects, users])
    engine.dispose()
