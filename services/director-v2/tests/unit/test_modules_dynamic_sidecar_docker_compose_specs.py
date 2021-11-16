# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import yaml
from simcore_service_director_v2.modules.dynamic_sidecar.docker_compose_specs import (
    _environment_section,
)


def test_parse_and_export_of_compose_environment_section():
    # sample from https://docs.docker.com/compose/compose-file/compose-file-v3/#environment

    compose_as_dict = yaml.safe_load(
        """
environment:
  RACK_ENV: development
  SHOW: 'true'
  SESSION_SECRET:
    """
    )
    assert isinstance(compose_as_dict["environment"], dict)

    compose_as_list_str = yaml.safe_load(
        """
environment:
  - RACK_ENV=development
  - SHOW=true
  - SESSION_SECRET
    """
    )

    assert isinstance(compose_as_list_str["environment"], list)

    assert _environment_section.parse(
        compose_as_dict["environment"]
    ) == _environment_section.parse(compose_as_list_str["environment"])

    assert (
        _environment_section.parse(compose_as_list_str["environment"])
        == compose_as_dict["environment"]
    )

    envs = _environment_section.export_as_list(compose_as_dict["environment"])
    assert envs == compose_as_list_str["environment"]
