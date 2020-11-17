#!/bin/python

""" Update a docker-compose file with json files in a path

    Usage: python update_compose_labels --c docker-compose.yml -f folder/path

:return: error code
"""

import argparse
import json
import logging
import sys
from enum import IntEnum
from pathlib import Path
from typing import Dict

import yaml

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ExitCode(IntEnum):
    SUCCESS = 0
    FAIL = 1


def get_compose_file(compose_file: Path) -> Dict:
    with compose_file.open() as filep:
        return yaml.safe_load(filep)


def get_metadata_file(metadata_file: Path) -> Dict:
    with metadata_file.open() as fp:
        return yaml.safe_load(fp)


def stringify_metadata(metadata: Dict) -> Dict[str, str]:
    jsons = {}
    for key, value in metadata.items():
        jsons[f"io.simcore.{key}"] = json.dumps({key: value})
    return jsons


def update_compose_labels(compose_cfg: Dict, metadata: Dict[str, str]) -> bool:
    compose_labels = compose_cfg["services"]["{{ cookiecutter.project_slug }}"]["build"]["labels"]
    changed = False
    for key, value in metadata.items():
        if key in compose_labels:
            if compose_labels[key] == value:
                continue
        compose_labels[key] = value
        changed = True
    return changed


def main(args=None) -> int:
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument(
            "--compose", help="The compose file where labels shall be updated", type=Path, required=True)
        parser.add_argument("--metadata", help="The metadata yaml file",
                            type=Path, required=False, default="metadata/metadata.yml")
        options = parser.parse_args(args)
        log.info("Testing if %s needs updates using labels in %s",
                 options.compose, options.metadata)
        # get available jsons
        compose_cfg = get_compose_file(options.compose)
        metadata = get_metadata_file(options.metadata)
        json_metadata = stringify_metadata(metadata)
        if update_compose_labels(compose_cfg, json_metadata):
            log.info("Updating %s using labels in %s",
                     options.compose, options.metadata)
            # write the file back
            with options.compose.open('w') as fp:
                yaml.safe_dump(compose_cfg, fp, default_flow_style=False)
                log.info("Update completed")
        else:
            log.info("No update necessary")
        return ExitCode.SUCCESS
    except:  # pylint: disable=bare-except
        log.exception("Unexpected error:")
        return ExitCode.FAIL


if __name__ == "__main__":
    sys.exit(main())
