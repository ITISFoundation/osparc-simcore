import os


def update_apps_metadata():
    applications = [{
        "application": "osparc",
        "replacements": [{
            "search_text": "replace_me_og_title",
            "replace_text": "oSPARC"
        }, {
            "search_text": "replace_me_og_description",
            "replace_text": "open online simulations for Stimulating Peripheral Activity to Relieve Conditions"
        }, {
            "search_text": "replace_me_og_image",
            "replace_text": "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/master/services/static-webserver/client/source/resource/osparc/favicon-osparc.png"
        }]
    }, {
        "application": "s4l",
        "replacements": [{
            "search_text": "replace_me_og_title",
            "replace_text": "Sim4Life"
        }, {
            "search_text": "replace_me_og_description",
            "replace_text": "Computational life sciences platform that combines computable human phantoms, powerful physics solvers and advanced tissue models."
        }, {
            "search_text": "replace_me_og_image",
            "replace_text": "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/Sim4Life-head-default.png"
        }]
    }, {
        "application": "s4lacad",
        "replacements": [{
            "search_text": "replace_me_og_title",
            "replace_text": "Sim4Life Science"
        }, {
            "search_text": "replace_me_og_description",
            "replace_text": "Sim4Life for Science - Computational life sciences platform that combines computable human phantoms, powerful physics solvers and advanced tissue models."
        }, {
            "search_text": "replace_me_og_image",
            "replace_text": "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/Sim4Life-head-academy.png"
        }]
    }, {
        "application": "s4llite",
        "replacements": [{
            "search_text": "replace_me_og_title",
            "replace_text": "S4L Lite"
        }, {
            "search_text": "replace_me_og_description",
            "replace_text": "Sim4Life for Students - Computational life sciences platform that combines computable human phantoms, powerful physics solvers and advanced tissue models."
        }, {
            "search_text": "replace_me_og_image",
            "replace_text": "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/Sim4Life-head-lite.png"
        }]
    }, {
        "application": "tis",
        "replacements": [{
            "search_text": "replace_me_og_title",
            "replace_text": "TI Plan - IT'IS"
        }, {
            "search_text": "replace_me_og_description",
            "replace_text": "my osparc description"
        }, {
            "search_text": "replace_me_og_image",
            "replace_text": "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/master/services/static-webserver/client/source/resource/osparc/tip_splitimage.png"
        }]
    }]

    output_folders = [
        "source-output",
        "build-output"
    ]

    dirname = os.path.dirname(__file__)
    for i in applications:
        application = i.get("application")
        for output_folder in output_folders:
            filename = os.path.join(dirname, output_folder, "index.html")
            with open(filename, "r") as file:
                data = file.read()
                replacements = i.get("replacements")
                for j in replacements:
                    search_text = j.get("search_text")
                    replace_text = j.get("replace_text")
                    data = data.replace(search_text, replace_text) 

            with open(filename, "w") as file: 
                print(f"Updating {application}'s index.html")
                file.write(data)


if __name__ == "__main__":
    update_apps_metadata()
