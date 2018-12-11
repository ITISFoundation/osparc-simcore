import json
import shutil
import tarfile
import tempfile
from pathlib import Path

from notebook.base.handlers import IPythonHandler
from notebook.utils import url_path_join
from simcore_sdk import node_ports


async def download_data(inputs_path):
    print("retrieving data...")
    PORTS = node_ports.ports()

    values = {}
    for port in PORTS.inputs:        
        if not port or port.value is None:
            continue
        print("downloading data from port '{}' with value '{}'...".format(port.key, port.value))
        value = await port.get()
        values[port.key] = {"key": port.key, "value": value}

        if "data:" in port.type:
            dest = inputs_path / port.key
            dest.mkdir(exist_ok=True, parents=True)
            dest = dest / Path(value).name
            shutil.move(value, dest)
            values[port.key] = {"key": port.key, "value": str(dest)}

    values_file = inputs_path / "key_values.json"
    with values_file.open('w') as fp:
        json.dump(values, fp)

async def upload_data(outputs_path):
    print("retrieving data...")
    PORTS = node_ports.ports()

    values = {}
    for port in PORTS.outputs:        
        print("uploading data from port '{}' with value '{}'...".format(port.key, port.value))
        value = await port.get()
        values[port.key] = {"key": port.key, "value": value}

        if "data:" in port.type:
            src_folder = outputs_path / port.key
            list_files = list(src_folder.glob("*.*"))
            if len(list_files) == 1:
                # directly upload
                await port.set(list_files[0])
            else:
                temp_file = tempfile.NamedTemporaryFile(suffix=".tgz")
                temp_file.close()
                with tarfile.open(temp_file.name, mode='w:gz') as tar_ptr:
                    for file_path in list_files:
                        tar_ptr.add(file_path, arcname=file_path.name, recursive=False)
                await port.set(temp_file.name)
                Path(temp_file).unlink()

class RetrieveHandler(IPythonHandler):

    async def initialize(self):
        self.inputs_path = Path("~/inputs").expanduser()
        self.outputs_path = Path("~/outputs").expanduser()
        create_ports_sub_folders(self.inputs_path)
        create_ports_sub_folders(self.outputs_path)

        def create_ports_sub_folders(ports: node_ports._items_list.ItemsList, parent_path: Path):
            for port in ports:
                if "data:" in port.type:
                    sub_folder = parent_path / port.key
                    sub_folder.mkdir(exist_ok=True, parents=True)

    async def get(self):
        await download_data(self.inputs_path)
        await upload_data(self.outputs_path)
        self.finish('completed retrieve!')


class SaveHandler(IPythonHandler):
    async def post(self):
        notebooks_path = Path("~/notebooks").expanduser()
        # collect all notebooks here
        NODE = node_ports.node()
        NODE.save_state
        self.finish('completed save!')
        

def load_jupyter_server_extension(nb_server_app):
    """
    Called when the extension is loaded.

    Args:
        nb_server_app (NotebookWebApplication): handle to the Notebook webserver instance.
    """
    web_app = nb_server_app.web_app
    host_pattern = '.*$'
    route_pattern = url_path_join(web_app.settings['base_url'], '/retrieve')
    
    web_app.add_handlers(host_pattern, [(route_pattern, RetrieveHandler)])

    route_pattern = url_path_join(web_app.settings['base_url'], '/save')
    
    web_app.add_handlers(host_pattern, [(route_pattern, RetrieveHandler)])
