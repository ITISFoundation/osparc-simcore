from collections import UserDict
from pathlib import Path
from string import Template
from typing import Any

import pytest
import yaml
from service_integration.compose_spec_model import ComposeSpecification


@pytest.fixture
def compose_spec_data(tests_data_dir: Path) -> dict[str, Any]:
    content = (tests_data_dir / "compose-spec.yml").read_text()
    return yaml.safe_load(content)


class SubstitutionsDict(UserDict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.used = set()  # used keys

    def __getitem__(self, key) -> Any:
        value = super().__getitem__(key)
        self.used.add(key)
        return value

    @property
    def unused(self):
        return {key for key in self.keys() if key not in self.used}


def test_string_templates():

    substitutions = SubstitutionsDict(
        {
            "OSPARC_SETTINGS_USER_API_KEY": "123456",
            "OSPARC_SETTINGS_USER_EMAIL": "user@email.com",
        }
    )
    template = Template(
        "x=${OSPARC_SETTINGS_USER_EMAIL} x=$OSPARC_SETTINGS_USER_EMAIL but $undefined or unused $$OSPARC_SETTINGS_USER_API_KEY"
    )
    result: str = template.safe_substitute(substitutions)

    assert substitutions.used == {"OSPARC_SETTINGS_USER_EMAIL"}
    assert substitutions.unused == {"OSPARC_SETTINGS_USER_API_KEY"}

    # NOTE in py 3.11:  Template("${OSPARC_SETTINGS_USER_EMAIL}").get_identifiers()
    assert (
        result
        == "x=user@email.com x=user@email.com but $undefined or unused $OSPARC_SETTINGS_USER_API_KEY"
    )


@pytest.mark.skip(reason="DEV")
def test_it(compose_spec_data: dict[str, Any]):

    compose_spec = ComposeSpecification.parse_obj(compose_spec_data)

    for service in compose_spec.services or []:
        assert service  # nosec

        if service.environment:
            if isinstance(service.environment, dict):
                for key, value in service.environment.items():
                    pass
