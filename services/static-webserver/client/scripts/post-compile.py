import os
import json


output_folders = [
    "source-output", # dev output
    "build-output",  # default production output
    "build-client"   # I believe we create the production outputs here
]


def read_json_file(filename):
    dirname = os.path.dirname(__file__)
    meta_filename = os.path.join(dirname, filename)
    with open(meta_filename, "r") as file:
        metadata = json.load(file)
        return metadata["applications"]


def update_apps_metadata():
    dirname = os.path.dirname(__file__)
    applications = read_json_file("apps_metadata.json")
    for i in applications:
        application = i.get("application")
        for output_folder in output_folders:
            filename = os.path.join(dirname, '..', output_folder, application, "index.html")
            if not os.path.isfile(filename):
                continue
            with open(filename, "r") as file:
                data = file.read()
                replacements = i.get("replacements")
                for key in replacements:
                    replace_text = replacements[key]
                    data = data.replace(key, replace_text)
            with open(filename, "w") as file: 
                print(f"Updating app metadata: {filename}")
                file.write(data)


if __name__ == "__main__":
    update_apps_metadata()
