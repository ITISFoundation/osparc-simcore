#pylint: disable=C0111
def update_config_file(path, config):
    import json
    with open(path, "w") as json_file:
        json.dump(config, json_file)

def get_empty_config():
    return {
        "version": "0.1",
        "inputs": [
        ],
        "outputs": [
        ]
    }
