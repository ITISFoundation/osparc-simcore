# pylint:disable = redefined-outer-name

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import pytest
import requests
from fastapi import status
from pydantic import parse_file_as
from simcore_service_director_v2.models.schemas.dynamic_services import SchedulerData
from tenacity import Retrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed


@pytest.fixture
def legacy_scheduler_data_format(mocks_dir: Path) -> Path:
    fake_service_path = mocks_dir / "legacy_scheduler_data_format.json"
    assert fake_service_path.exists()
    return fake_service_path


def test_regression_as_label_data(scheduler_data: SchedulerData) -> None:
    # old tested implementation
    scheduler_data_copy = deepcopy(scheduler_data)
    scheduler_data_copy.compose_spec = json.dumps(scheduler_data_copy.compose_spec)
    json_encoded = scheduler_data_copy.json()

    # using pydantic's internals
    label_data = scheduler_data.as_label_data()

    parsed_json_encoded = SchedulerData.parse_raw(json_encoded)
    parsed_label_data = SchedulerData.parse_raw(label_data)
    assert parsed_json_encoded == parsed_label_data


def test_ensure_legacy_format_compatibility(legacy_scheduler_data_format: Path):
    # Ensure no further PRs can break this format

    # PRs applying changes to the legacy format:
    # - https://github.com/ITISFoundation/osparc-simcore/pull/3610
    assert parse_file_as(list[SchedulerData], legacy_scheduler_data_format)


@dataclass
class DeprecatedPRInfo:
    pr_number: int

    @property
    def issue_match(self) -> str:
        return f"#{self.pr_number}"

    @property
    def pr_deprecation_message(self) -> str:
        return (
            "Please search for all occurrences of "
            f"https://github.com/ITISFoundation/osparc-simcore/pull/{self.pr_number} "
            "and follow the instructions on how to remove deprecated code. "
            "Also remember to remove the related `DeprecatedPRInfo` entry."
        )


@pytest.mark.parametrize(
    "deprecated_pr_info",
    [
        DeprecatedPRInfo(pr_number=3610),
    ],
)
async def test_fail_if_code_is_released_to_production(
    deprecated_pr_info: DeprecatedPRInfo,
):
    _RELEASE_ENTRIES = 50
    releases_data: list[dict] = []
    for attempt in Retrying(wait=wait_fixed(1), stop=stop_after_attempt(5)):
        with attempt:
            result = requests.get(
                "https://api.github.com/repos/itisfoundation/osparc-simcore/releases",
                params=dict(per_page=_RELEASE_ENTRIES),
                timeout=10,
            )
            assert result.status_code == status.HTTP_200_OK
            releases_data: list[dict] = json.loads(result.text)

    production_releases = [
        x for x in releases_data if x["draft"] is False and x["prerelease"] is False
    ]

    assert len(production_releases) > 1
    for release_data in production_releases:
        if deprecated_pr_info.issue_match in release_data["body"]:
            raise RuntimeError(deprecated_pr_info.pr_deprecation_message)
