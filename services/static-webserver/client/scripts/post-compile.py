import json
import os
import random
from pathlib import Path

output_folders = [
    "source-output",  # dev output
    "build-output",  # default production output
    "build-client",  # I believe we create the production outputs here
]


def _get_applications_from_metadata():
    dirname = os.path.dirname(__file__)
    meta_filename = os.path.join(dirname, "apps_metadata.json")
    with open(meta_filename) as file:
        metadata = json.load(file)
        return metadata["applications"]


def update_apps_metadata():
    dirname = os.path.dirname(__file__)
    applications = _get_applications_from_metadata()
    for i in applications:
        application = i.get("application")
        for output_folder in output_folders:
            index_file_path = Path(dirname).joinpath(
                "..", output_folder, application, "index.html"
            )
            if os.path.isfile(index_file_path):
                print(f"Updating app metadata: {index_file_path.resolve()}")
                replacements = i.get("replacements")
                for key in replacements:
                    replace_text = replacements[key]
                    index_file_path.write_text(
                        index_file_path.read_text().replace(
                            "${" + key + "}",
                            replace_text,
                        )
                    )


def _get_output_file_paths(filename):
    output_file_paths: list[Path] = []
    dirname = os.path.dirname(__file__)
    applications = _get_applications_from_metadata()
    for i in applications:
        application = i.get("application")
        for output_folder in output_folders:
            result = Path(dirname).joinpath("..", output_folder, application, filename)
            if result.is_file():
                output_file_paths.append(result)
    return output_file_paths


def add_no_cache_param(vcs_ref_client):
    index_file_paths = _get_output_file_paths("index.html")
    for index_file_path in index_file_paths:
        print(f"Updating vcs_ref_client: {index_file_path.resolve()}")
        index_file_path.write_text(
            index_file_path.read_text().replace(
                "${boot_params}",
                "nocache=" + vcs_ref_client,
            )
        )

    boot_file_paths = _get_output_file_paths("boot.js")
    for boot_file_path in boot_file_paths:
        print(f"Updating addNoCacheParam URL_PARAMETERS: {boot_file_path.resolve()}")
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
