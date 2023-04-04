import os
import sys
import yaml

DIR_PATH = os.path.dirname(os.path.realpath(__file__))
source_file_name = sys.argv[1]
target_file_name = sys.argv[2]
file_source_path = DIR_PATH + f"/../{source_file_name}"
file_target_path = DIR_PATH + f"/../{target_file_name}"

with open(file_source_path, "r") as stream:
    try:
        data = yaml.safe_load(stream)
        data.pop("definitions", None)
        yaml.dump(data, open(file_target_path, "w"))
    except yaml.YAMLError as exc:
        print(exc)
