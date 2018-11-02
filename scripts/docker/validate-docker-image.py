# Build the docker image to validate
# Usage: python validate-docker-image.py %IMAGE_NAME:TAG% %NODE_SCHEMA_PATH%

import argparse
import json
import logging
import sys
from pathlib import Path

import docker
from jsonschema import SchemaError, ValidationError, validate


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def get_docker_image_labels(dockerimage: str):
    client = docker.from_env()

    image = client.images.get(dockerimage)
    return image.labels

def validate_docker_image(dockerimage: str, schema: Path):
    docker_labels = get_docker_image_labels(dockerimage)
    if docker_labels:
        log.info("Found docker labels in image %s", dockerimage)
        image_tags = {}
        for key in docker_labels.keys():
            if key.startswith("io.simcore."):
                try:
                    label_data = json.loads(docker_labels[key])
                except json.JSONDecodeError:
                    log.exception("Invalid json label %s", docker_labels[key])
                    raise
                for label_key in label_data.keys():
                    image_tags[label_key] = label_data[label_key]

        if image_tags:
            log.info("Found image tags in docker image")
            if not schema.exists():
                log.error("The file path to the schema is invalid!")
                return
            with schema.open() as fp:
                schema_specs = json.load(fp)
                log.info("Loaded schema specifications, validating...")
                try:
                    validate(image_tags, schema_specs)
                    log.info("%s is valid against %s! Congratulations!!", dockerimage, str(schema))
                except SchemaError:
                    log.exception("Invalid schema!")
                except ValidationError:
                    log.exception("Invalid image!")
                    
                


parser = argparse.ArgumentParser(description="Validate docker labels of an oSparc service using a jsonschema as parameter.")
parser.add_argument("dockerimage", help="The docker image full key:tag", type=str)
parser.add_argument("jsonschema", help="The path to the corresponding jsonschema file to validate with", type=Path)
args = sys.argv[1:]
options = parser.parse_args(args)

validate_docker_image(options.dockerimage, 
                    options.jsonschema)
