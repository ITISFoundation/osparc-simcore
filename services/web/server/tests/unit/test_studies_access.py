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




@pytest.mark.travis
def test_WHILE_DEVELOPMENT():

    from simcore_service_webserver.studies_access import TEMPLATE_PREFIX
    user_id = 55

    def _replace_uuids(node):
        if isinstance(node, str):
            if node.startswith(TEMPLATE_PREFIX):
                node = compose_uuid(node, user_id)
        elif isinstance(node, list):
            node = [_replace_uuids(item) for item in node]
        elif isinstance(node, dict):
            _frozen_items = tuple(node.items())
            for key, value in _frozen_items:
                if isinstance(key, str):
                    if key.startswith(TEMPLATE_PREFIX):
                        new_key = compose_uuid(key, user_id)
                        node[new_key] = node.pop(key)
                        key = new_key
                node[key] = _replace_uuids(value)
        return node


    data = {
        TEMPLATE_PREFIX+'asdfasdf': TEMPLATE_PREFIX+'asdfasdf'
    }
    got = _replace_uuids(data)
    assert list(got.keys()) == list(got.values())


    got1 = _replace_uuids([data, data])
    assert isinstance(got1, list)
    assert got1 == [got, got]


    prjs = isan_template_projects()
    assert TEMPLATE_PREFIX in str(prjs)

    new_prjs = _replace_uuids(prjs)
    assert TEMPLATE_PREFIX not in str(new_prjs)
