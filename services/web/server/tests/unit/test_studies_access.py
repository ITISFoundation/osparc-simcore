""" Covers user stories for ISAN : #501, #712, #730

"""
# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from simcore_service_webserver.studies_access import create_project_from_template, compose_uuid

from simcore_service_webserver.resources import resources

import json
import pytest



def isan_template_projects():
    projects = []
    with resources.stream('data/fake-template-projects.isan.json') as fp:
        projects = json.load(fp)
    return projects


@pytest.mark.parametrize("name,template_project",
    [(p['name'], p) for p in isan_template_projects()[-1:]] )
def test_create_from_template(name, template_project):

    user = {
        'id': 0,
        'name': 'foo',
        'email': 'foo@b.com'
    }

    project = create_project_from_template(template_project, user)

    assert project["prj_owner"] == user["name"], "did not mark user's ownership"

    # if this template is taken by the same user, it returns smae project
    expected_project_uuid = compose_uuid(template_project["uuid"], user["id"])
    assert project["uuid"] == expected_project_uuid
