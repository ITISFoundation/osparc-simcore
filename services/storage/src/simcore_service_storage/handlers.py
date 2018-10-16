import time

from aiohttp import web

from servicelib.rest_utils import extract_and_validate

from . import __version__
from .rest_models import FileMetaDataSchema
from .session import get_session

#FIXME: W0613: Unused argument 'request' (unused-argument)
#pylint: disable=W0613

#FIXME: W0612:Unused variable 'fileId'
# pylint: disable=W0612

file_schema  = FileMetaDataSchema()
files_schema = FileMetaDataSchema(many=True)

async def check_health(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert not params
    assert not query
    assert not body

    # we play with session here
    session = await get_session(request)
    data = {
        'name':__name__.split('.')[0],
        'version': __version__,
        'status': 'SERVICE_RUNNING',
        'last_access' : session.get("last", -1.)
    }

    #TODO: servicelib.create_and_validate_response(data)

    session["last"] = time.time()
    return data

async def check_action(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params
    assert query, "query %s" % query
    assert body, "body %s" % body

    if params['action'] == 'fail':
        raise ValueError("some randome failure")

    # echo's input FIXME: convert to dic
    # FIXME: output = fake_schema.dump(body)
    output = {
    "path_value" : params.get('action'),
    "query_value": query.get('data'),
    "body_value" :{
        "key1": 1, #body.body_value.key1,
        "key2": 0  #body.body_value.key2,
        }
    }
    return output

async def get_files_metadata(request: web.Request):
    data1 = {
        'filename' : "a.txt",
        'version': '1.0',
        'last_accessed' : 1234.2,
        'owner' : 'c8da5f29-6906-4d0f-80b1-0dc643d6303d',
        'storage_location' : 'simcore.s3'
    }

    data2 = {
        'filename' : "a.txt",
        'version': '1.0',
        'last_accessed' : 1234.2,
        'owner' : 'c8da5f29-6906-4d0f-80b1-0dc643d6303d',
        'storage_location' : 'simcore.s3'
    }

    #return files_schema.dump([db_data1, db_data1])
    return [data1, data2]

async def get_file_metadata(request: web.Request):
    path_params, query_params, body = await extract_and_validate(request)

    assert path_params
    assert not query_params
    assert not body

    fileId = path_params['fileId']

    data = {
        'filename' : "a.txt",
        'version': '1.0',
        'last_accessed' : 1234.2,
        'owner' : 'c8da5f29-6906-4d0f-80b1-0dc643d6303d',
        'storage_location' : 'simcore.s3'
    }
    return data

async def update_file_meta_data(request: web.Request):

    path_params, query_params, body = await extract_and_validate(request)

    assert path_params
    assert not query_params
    assert not body

    fileId = path_params['fileId']

    data = {
        'filename' : "a.txt",
        'version': '1.0',
        'last_access' : 1234.2,
        'owner' : 'c8da5f29-6906-4d0f-80b1-0dc643d6303d',
        'storage_location' : 'simcore.s3'
    }
    return data

async def download_file(request: web.Request):

    path_params, query_params, body = await extract_and_validate(request)

    assert path_params
    assert not query_params
    assert not body

    fileId = path_params['fileId']

    data = {
        'filename' : "a.txt",
        'version': '1.0',
        'last_access' : 1234.2,
        'owner' : 'c8da5f29-6906-4d0f-80b1-0dc643d6303d',
        'storage_location' : 'simcore.s3'
    }
    return data

async def upload_file(request: web.Request):

    path_params, query_params, body = await extract_and_validate(request)

    assert path_params
    assert not query_params
    assert not body

    fileId = path_params['fileId']

    data = {
        'filename' : "a.txt",
        'version': '1.0',
        'last_access' : 1234.2,
        'owner' : 'c8da5f29-6906-4d0f-80b1-0dc643d6303d',
        'storage_location' : 'simcore.s3'
    }
    return data

async def delete_file(request: web.Request):
    path_params, query_params, body = await extract_and_validate(request)

    assert path_params
    assert not query_params
    assert not body

    fileId = path_params['fileId']

    data = {
        'filename' : "a.txt",
        'version': '1.0',
        'last_access' : 1234.2,
        'owner' : 'c8da5f29-6906-4d0f-80b1-0dc643d6303d',
        'storage_location' : 'simcore.s3'
    }
    return data
