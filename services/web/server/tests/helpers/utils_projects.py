""" helpers to manage the projects's database and produce fixtures/mockup data for testing


SEE services/web/server/src/simcore_service_webserver/projects/projects_models.py

"""
# pylint: disable=no-value-for-parameter

import json
import re
from typing import Dict

from aiohttp import web

from simcore_service_webserver.projects.projects_models import \
    ProjectDB as storage
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


async def delete_all_projects(engine):
    from simcore_service_webserver.projects.projects_models import projects, user_to_projects

    async with engine.acquire() as conn:
        query = user_to_projects.delete()
        await conn.execute(query)

        query = projects.delete()
        await conn.execute(query)


class NewProject:
    def __init__(self, params: Dict=None, app: web.Application=None, clear_all=True):
        self.params = params
        self.engine = app[APP_DB_ENGINE_KEY]
        self.prj = {}
        self.clear_all = clear_all

        if not self.clear_all:
            # TODO: add delete_project. Deleting a single project implies having to delete as well all dependencies created
            raise ValueError("UNDER DEVELOPMENT: Currently can only delete all projects ")

    async def __aenter__(self):
        self.prj = await create_project(self.engine, self.params)
        return self.prj

    async def __aexit__(self, *args):
        if self.clear_all:
            await delete_all_projects(self.engine)
