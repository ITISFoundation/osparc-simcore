from aiohttp import web

from .session import get_session
import time

from .rest.generated_code.models import FileMetaData

__version__ = "0.0.0"

async def health_check(request):
    session = await get_session(request)

    data = {
        'name':__name__.split('.')[0], 
        'version': __version__,
        'status': 'RUNNING_FINE',
        'last_access' : session.get("last", -1.)
    }
    session["last"] = time.time()
    return web.json_response(data, status=200)

async def get_files_metadata(request):
    data1 = FileMetaData(**{
        'filename' : "a.txt",
        'version': '1.0',
        'last_accessed' : 1234.2,
        'owner' : 'c8da5f29-6906-4d0f-80b1-0dc643d6303d',
        'storage_location' : 'simcore.s3'
    })

    data2 = FileMetaData(**{
        'filename' : "a.txt",
        'version': '1.0',
        'last_accessed' : 1234.2,
        'owner' : 'c8da5f29-6906-4d0f-80b1-0dc643d6303d',
        'storage_location' : 'simcore.s3'
    })
    return [data1, data2]

async def get_file_metadata(request, fileId):
  
    data = FileMetaData(**{
        'filename' : "a.txt",
        'version': '1.0',
        'last_accessed' : 1234.2,
        'owner' : 'c8da5f29-6906-4d0f-80b1-0dc643d6303d',
        'storage_location' : 'simcore.s3'
    })
    return data

async def update_file_meta_data(request, fileId):
    data = {
        'filename' : "a.txt",
        'version': '1.0',
        'last_access' : 1234.2,
        'owner' : 'c8da5f29-6906-4d0f-80b1-0dc643d6303d',
        'storage_location' : 'simcore.s3'
    }
    return web.json_response(data, status=200)

async def download_file(request, fileId):
    data = {
        'filename' : "a.txt",
        'version': '1.0',
        'last_access' : 1234.2,
        'owner' : 'c8da5f29-6906-4d0f-80b1-0dc643d6303d',
        'storage_location' : 'simcore.s3'
    }
    return web.json_response(data, status=200)

async def upload_file(request, fileId):
    data = {
        'filename' : "a.txt",
        'version': '1.0',
        'last_access' : 1234.2,
        'owner' : 'c8da5f29-6906-4d0f-80b1-0dc643d6303d',
        'storage_location' : 'simcore.s3'
    }
    return web.json_response(data, status=200)

async def delete_file(request, fileId):
    data = {
        'filename' : "a.txt",
        'version': '1.0',
        'last_access' : 1234.2,
        'owner' : 'c8da5f29-6906-4d0f-80b1-0dc643d6303d',
        'storage_location' : 'simcore.s3'
    }
    return web.json_response(data, status=200)