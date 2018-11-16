import json
import logging

from aiohttp import web

from .login.decorators import RQT_USERID_KEY, login_required

log = logging.getLogger(__name__)







project_sample = {
    'projectUuid': '07640335-a91f-468c-ab69-a374fa82078d',
    'name': 'Sample Project',
    'description': 'A little fake project without actual backend',
    'notes': '# title\nThere be dragons inside',
    'owner': 'TOBI',
    'collaborators': {
        'PEDRO': [
            'read',
            'write'
        ]
    },
    'creationDate': '2018-07-02T16:01:00Z',
    'lastChangeDate': '2018-07-02T16:02:22Z',
    'thumbnail': 'https://placeimg.com/171/96/tech/grayscale/?0.jpg',
    'workbench': {
        'UUID1': {
            'key': 'services/dynamic/itis/file-picker',
            'version': '0.0.0',
            'outputs': {
                'outFile': {
                    'store': 's3-z43',
                    'path': '/bucket1/file1'
                }
            },
            'position': {
                        'x': 10,
                        'y': 10
                    }
        },
    }
}


@login_required
async def list_projects(request: web.Request):
    log.debug('user %s', request[RQT_USERID_KEY])
    project_samples = [project_sample, ] * 3
    return project_samples


@login_required
async def create_projects(request: web.Request):
    log.debug('user %s', request[RQT_USERID_KEY])
    raise web.HTTPCreated(text=json.dumps(project_sample),
                          content_type='application/json')


@login_required
async def get_project(request: web.Request):
    log.debug('user %s', request[RQT_USERID_KEY])
    return project_sample


@login_required
async def update_project(request: web.Request):
    log.debug('user %s', request[RQT_USERID_KEY])
    raise NotImplementedError('%s still not implemented' % request)


@login_required
async def delete_project(request: web.Request):
    log.debug('user %s', request[RQT_USERID_KEY])
    raise NotImplementedError('%s still not implemented' % request)

    #raise web.HTTPNoContent()
