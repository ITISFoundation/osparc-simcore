import json
import random
import re
from typing import Dict

from sqlalchemy.sql import and_, select

from aiohttp import web
# SEE services/web/server/src/simcore_service_webserver/projects/projects_models.py
from simcore_service_webserver.projects.projects_models import \
    ProjectDB as storage
from simcore_service_webserver.projects.projects_models import ProjectType
from simcore_service_webserver.resources import resources
from simcore_service_webserver.db import APP_DB_ENGINE_KEY


fake_template_resources = ['data/'+name for name in resources.listdir('data')
    if re.match(r"^fake-template-(.+).json", name) ]

fake_project_resources = ['data/'+name for name in resources.listdir('data')
    if re.match(r"^fake-user-(.+).json", name) ]


def load_data(name):
    with resources.stream(name) as fp:
        return json.load(fp)


async def create_project(engine, params: Dict=None, user_id=None) -> Dict:
    params = params or {}

    prj = load_data('data/fake-template-projects.isan.json')[0]
    prj.update(params)

    await storage.add_project(prj, user_id, engine)
    return prj


async def delete_project(engine, project_uuid):
    """ WARNING: does not delete entries from user_to_projects

    """
    #pylint: disable=no-value-for-parameter
    from simcore_service_webserver.projects.projects_models import projects

    # TODO: cleanup first user_to_projects
    async with engine.acquire() as conn:
        query = projects.delete().\
            where(projects.c.uuid == project_uuid)
        await conn.execute(query)



class NewProject:
    def __init__(self, params: Dict=None, app: web.Application=None):
        self.params = params
        self.engine = app[APP_DB_ENGINE_KEY]
        self.prj = {}

    async def __aenter__(self):
        self.prj = await create_project(self.engine, self.params)
        return self.prj

    async def __aexit__(self, *args):
        project_uuid = self.prj["uuid"]
        if project_uuid:
            await delete_project(self.engine, project_uuid)
