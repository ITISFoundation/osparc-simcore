""" fake data for testing

"""
import json
import logging
from collections import defaultdict, namedtuple
from copy import deepcopy

from ..resources import resources

log = logging.getLogger(__name__)

class Fake:
    """ Holds fake database of projects and its association to users
        for testing purposes

        Keeps also generated data
    """
    # TODO: auto generate data from specs and faker tool. Use http://json-schema-faker.js.org

    ProjectItem = namedtuple("ProjectItem", "id template data".split())

    # fake databases
    projects = {} # project_id -> ProjectItem
    user_to_projects_map = defaultdict(list) # user_id -> [project_id, ...]


    @classmethod
    def add_projects(cls, projects, user_id=None):
        """ adds all projects and assigns to a user

        """
        for prj in projects:
            pid = prj['projectUuid']
            cls.projects[pid] = cls.ProjectItem(id=pid, template=user_id is None, data=deepcopy(prj))
            if user_id is not None:
                cls.user_to_projects_map[user_id].append(pid)

    @classmethod
    def load_user_projects(cls, user_id=None):
        """ adds a project per user """
        with resources.stream("data/fake-user-projects.json") as f:
            projects = json.load(f)

        for i, prj in enumerate(projects):
            pid, uid = prj['projectUuid'], i if not user_id else user_id
            cls.projects[pid] = cls.ProjectItem(id=pid, template=False, data=prj)
            cls.user_to_projects_map[uid].append(pid)

    @classmethod
    def load_template_projects(cls):
        template_file = "data/fake-template-projects.json"
        with resources.stream(template_file) as f:
            projects = json.load(f)
        template_osparc_file = "data/fake-template-projects.osparc.json"
        with resources.stream(template_osparc_file) as f:
            projects = projects + json.load(f)

        for prj in projects:
            pid = prj['projectUuid']
            cls.projects[pid] =  cls.ProjectItem(id=pid, template=True, data=prj)

    @classmethod
    def reset(cls):
        cls.projects = {}
        cls.user_to_projects_map = defaultdict(list)
