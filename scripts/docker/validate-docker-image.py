# Build the docker image to validate
# Usage: python validate-docker-image.py %IMAGE_NAME:TAG% %NODE_SCHEMA_PATH%

import argparse
import json
import sys
from pathlib import Path

import docker
from jsonschema import validate


def get_docker_image_labels(dockerimage: str):
    client = docker.from_env()

    image = client.images.get(dockerimage)
    return image.labels

def validate_docker_image(dockerimage: str, schema: Path):
    docker_labels = get_docker_image_labels(dockerimage)
    if docker_labels:
        image_tags = {}
        for key in docker_labels.keys():
            if key.startswith("io.simcore."):
                label_data = json.loads(docker_labels[key])
                for label_key in label_data.keys():
                    image_tags[label_key] = label_data[label_key]

        if image_tags:
            with schema.open() as fp:
                schema_specs = json.load(fp)
                validate(image_tags, schema_specs)
                print("validated!")


parser = argparse.ArgumentParser(description="Validate docker labels of an oSparc service using a jsonschema as parameter.")
parser.add_argument("dockerimage", help="The docker image full key:tag", type=str)
parser.add_argument("jsonschema", help="The path to the corresponding jsonschema file to validate with", type=Path)
args = sys.argv[1:]
options = parser.parse_args(args)

validate_docker_image(options.dockerimage, 
                    options.jsonschema)
