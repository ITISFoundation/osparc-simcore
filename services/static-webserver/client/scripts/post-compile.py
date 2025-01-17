import json
import os
import random
import sys

output_folders = [
    "source-output",  # dev output
    "build-output",  # default production output
    "build-client",  # I believe we create the production outputs here
]


def _read_json_file(filename):
    dirname = os.path.dirname(__file__)
    meta_filename = os.path.join(dirname, filename)
    with open(meta_filename) as file:
        metadata = json.load(file)
        return metadata["applications"]


def update_apps_metadata():
    dirname = os.path.dirname(__file__)
    applications = _read_json_file("apps_metadata.json")
    for i in applications:
        application = i.get("application")
        replacements = i.get("replacements")
        for output_folder in output_folders:
            filename = os.path.join(
                dirname, "..", output_folder, application, "index.html"
            )
            if not os.path.isfile(filename):
                continue
            with open(filename) as file:
                data = file.read()
                for key in replacements:
                    replace_text = replacements[key]
                    data = data.replace("${" + key + "}", replace_text)
            with open(filename, "w") as file:
                print(f"Updating app metadata: {filename}")
                file.write(data)


def _get_index_file_paths():
    index_file_paths = []
    dirname = os.path.dirname(__file__)
    applications = _read_json_file("apps_metadata.json")
    for i in applications:
        application = i.get("application")
        for output_folder in output_folders:
            index_file_paths.append(
                os.path.join(dirname, "..", output_folder, application, "index.html")
            )
    return index_file_paths


def add_no_cache_param(vcs_ref_client):
    index_file_paths = _get_index_file_paths()
    for index_file_path in index_file_paths:
        if not os.path.isfile(index_file_path):
            continue
        with open(index_file_path) as index_file:
            data = index_file.read()
            if vcs_ref_client:
                data = data.replace("vcs_ref_client", vcs_ref_client)
            else:
                random.seed(5)
                data = data.replace("vcs_ref_client", str(random.random()))
        with open(index_file_path, "w") as file:
            print(f"Updating vcs_ref_client: {index_file_path}")
            file.write(data)


if __name__ == "__main__":
    update_apps_metadata()
    vcs_ref_client = None
    if len(sys.argv) > 1:
        vcs_ref_client = sys.argv[1]
    add_no_cache_param(vcs_ref_client)
