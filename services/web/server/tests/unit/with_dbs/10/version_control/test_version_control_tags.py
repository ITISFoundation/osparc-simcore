from faker import Faker
from simcore_service_webserver.version_control_tags import (
    compose_wcopy_project_tag_name,
    parse_wcopy_project_tag_name,
)


def test_parse_and_compose_tag_names(faker: Faker):

    wcopy_project_id = faker.uuid4(cast_to=None)

    tag = compose_wcopy_project_tag_name(wcopy_project_id)
    assert parse_wcopy_project_tag_name(tag) == wcopy_project_id
