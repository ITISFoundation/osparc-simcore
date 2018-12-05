import json
import shutil
from pathlib import Path

from notebook.base.handlers import IPythonHandler
from notebook.utils import url_path_join
from simcore_sdk import node_ports


async def retrieve_data():
    print("retrieving data...")
    PORTS = node_ports.ports()

    inputs_path = Path("~/inputs").expanduser()
    inputs_path.mkdir(exist_ok=True)

    values = {}
    for node_input in PORTS.inputs:        
        if not node_input or node_input.value is None:
            continue
        print("getting data from port '{}' with value '{}'...".format(node_input.key, node_input.value))
        value = await node_input.get()
        values[node_input.key] = {"type": node_input.type, "value": value}

        if "data:" in node_input.type:
            dest = inputs_path / node_input.key
            dest.mkdir(exist_ok=True, parents=True)
            dest = dest / Path(value).name
            shutil.move(value, dest)
            values[node_input.key] = {"type": node_input.type, "value": str(dest)}

    values_file = inputs_path / "values.json"
    with values_file.open('w') as fp:
        json.dump(values, fp)


class HelloWorldHandler(IPythonHandler):
    async def get(self):
        await retrieve_data()
        self.finish('Hello, world!')
        

def load_jupyter_server_extension(nb_server_app):
    """
    Called when the extension is loaded.

    Args:
        nb_server_app (NotebookWebApplication): handle to the Notebook webserver instance.
    """
    web_app = nb_server_app.web_app
    host_pattern = '.*$'
    route_pattern = url_path_join(web_app.settings['base_url'], '/hello')
    
    web_app.add_handlers(host_pattern, [(route_pattern, HelloWorldHandler)])
