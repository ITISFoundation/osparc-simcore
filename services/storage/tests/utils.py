from contextlib import contextmanager

import requests
import sqlalchemy as sa

import simcore_service_storage_sdk
from simcore_service_storage.models import FileMetaData, file_meta_data

DATABASE = 'aio_login_tests'
USER = 'admin'
PASS = 'admin'

ACCESS_KEY = '12345678'
SECRET_KEY = '12345678'

BUCKET_NAME ="simcore-testing"


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

@contextmanager
def api_client(cfg: simcore_service_storage_sdk.Configuration) -> simcore_service_storage_sdk.ApiClient:
    from simcore_service_storage_sdk.rest import ApiException

    client = simcore_service_storage_sdk.ApiClient(cfg)
    try:
        yield client
    except ApiException as err:
        print("%s\n" % err)
    finally:
        #NOTE: enforces to closing client session and connector.
        # this is a defect of the sdk
        del client.rest_client

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
        user_name= fmd.user_name)

    engine = sa.create_engine(url)
    conn = engine.connect()
    conn.execute(ins)
