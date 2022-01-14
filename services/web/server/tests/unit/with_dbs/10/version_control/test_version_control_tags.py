from faker import Faker
from simcore_service_webserver.version_control_tags import (
    compose_workcopy_project_tag_name,
    parse_workcopy_project_tag_name,
)


def test_parse_and_compose_tag_names(faker: Faker):

    workcopy_project_id = faker.uuid4(cast_to=None)

    tag = compose_workcopy_project_tag_name(workcopy_project_id)
    assert parse_workcopy_project_tag_name(tag) == workcopy_project_id
