import json
import os
import random
from pathlib import Path

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


def _get_output_file_paths(filename):
    output_file_paths: list[Path] = []
    dirname = os.path.dirname(__file__)
    applications = _read_json_file("apps_metadata.json")
    for i in applications:
        application = i.get("application")
        for output_folder in output_folders:
            result = Path(dirname).joinpath("..", output_folder, application, filename)
            if result.is_file():
                output_file_paths.append(result.resolve())
    return output_file_paths


def add_no_cache_param(vcs_ref_client):
    index_file_paths = _get_output_file_paths("index.html")
    for index_file_path in index_file_paths:
        print(f"Updating vcs_ref_client: {index_file_path}")
        index_file_path.write_text(
            index_file_path.read_text().replace(
                "${boot_params}",
                "nocache=" + vcs_ref_client,
            )
        )

    boot_file_paths = _get_output_file_paths("boot.js")
    for boot_file_path in boot_file_paths:
        print(f"Updating addNoCacheParam URL_PARAMETERS: {boot_file_path}")
        boot_file_path.write_text(
            boot_file_path.read_text().replace(
                "addNoCacheParam : false",
                "addNoCacheParam : true",
            )
        )


if __name__ == "__main__":
    update_apps_metadata()
    vcs_ref_client = os.getenv("VCS_REF_CLIENT", str(random.random()))
    add_no_cache_param(vcs_ref_client)
