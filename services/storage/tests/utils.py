from contextlib import contextmanager

import sqlalchemy as sa

import simcore_dsm_sdk
from simcore_service_storage.models import file_meta_data

BUCKET_NAME ="simcore-testing"


def create_tables(url, engine=None):
    meta = sa.MetaData()
    if not engine:
        engine = sa.create_engine(url)

    meta.create_all(bind=engine, tables=[file_meta_data])

@contextmanager
def api_client(cfg: simcore_dsm_sdk.Configuration) -> simcore_dsm_sdk.ApiClient:
    from simcore_dsm_sdk.rest import ApiException

    client = simcore_dsm_sdk.ApiClient(cfg)
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

def insert_metadata(url: str,
        object_name: str,
        bucket_name: str,
        file_id: str,
        file_name: str,
        user_id: int,
        user_name: str,
        location: str,
        project_id: int,
        project_name: str,
        node_id: int,
        node_name: str):
    #FIXME: E1120:No value for argument 'dml' in method call
    # pylint: disable=E1120
    ins = file_meta_data.insert().values(object_name=object_name,
        bucket_name=bucket_name,
        file_id=file_id,
        file_name=file_name,
        user_id=user_id,
        user_name=user_name,
        location=location,
        project_id=project_id,
        project_name=project_name,
        node_id=node_id,
        node_name=node_name)

    engine = sa.create_engine(url)
    conn = engine.connect()
    conn.execute(ins)
