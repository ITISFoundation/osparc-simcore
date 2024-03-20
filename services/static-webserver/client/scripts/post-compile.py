import os


def update_apps_metadata():
    applications = [
        {
            "application": "osparc",
             "replacements": {
                "replace_me_og_title": "oSPARC",
                "replace_me_og_description": "open online simulations for Stimulating Peripheral Activity to Relieve Conditions",
                "replace_me_og_image": "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/master/services/static-webserver/client/source/resource/osparc/favicon-osparc.png"
            },
        }, {
            "application": "s4l",
            "replacements": {
                "replace_me_og_title": "Sim4Life",
                "replace_me_og_description": "Computational life sciences platform that combines computable human phantoms, powerful physics solvers and advanced tissue models.",
                "replace_me_og_image": "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/Sim4Life-head-default.png"
            }
        }, {
            "application": "s4lacad",
            "replacements": {
                "replace_me_og_title": "Sim4Life Science",
                "replace_me_og_description": "Sim4Life for Science - Computational life sciences platform that combines computable human phantoms, powerful physics solvers and advanced tissue models.",
                "replace_me_og_image": "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/Sim4Life-head-academy.png"
            }
        }, {
            "application": "s4llite",
            "replacements": {
                "replace_me_og_title": "S4L Lite",
                "replace_me_og_description": "Sim4Life for Students - Computational life sciences platform that combines computable human phantoms, powerful physics solvers and advanced tissue models.",
                "replace_me_og_image": "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/Sim4Life-head-lite.png"
            }
        }, {
            "application": "tis",
            "replacements": {
                "replace_me_og_title": "TI Plan - IT'IS",
                "replace_me_og_description": "A tool powered by o²S²PARC technology that reduces optimization of targeted neurostimulation protocols.",
                "replace_me_og_image": "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/master/services/static-webserver/client/source/resource/osparc/tip_splitimage.png"
            }
        }
    ]

    output_folders = [
        "source-output", # dev output
        "build-output",  # default production output
        "build-client"   # I believe we create the production outputs here
    ]

    dirname = os.path.dirname(__file__)
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
