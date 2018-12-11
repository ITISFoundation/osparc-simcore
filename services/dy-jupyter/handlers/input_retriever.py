import json
import logging
import shutil
import tarfile
import tempfile
from pathlib import Path

from notebook.base.handlers import IPythonHandler
from notebook.utils import url_path_join

from simcore_sdk import node_ports

# logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

_FILE_TYPE_PREFIX = "data:"

async def download_data(inputs_path):
    logger.info("retrieving data from simcore...")
    PORTS = node_ports.ports()

    values = {}
    for port in PORTS.inputs:        
        if not port or port.value is None:
            continue
        logger.debug("downloading data from port '%s' with value '%s'...", port.key, port.value)
        value = await port.get()
        values[port.key] = {"key": port.key, "value": value}

        if _FILE_TYPE_PREFIX in port.type:
            dest = inputs_path / port.key
            dest.mkdir(exist_ok=True, parents=True)
            dest = dest / Path(value).name
            shutil.move(value, dest)
            values[port.key] = {"key": port.key, "value": str(dest)}

    values_file = inputs_path / "key_values.json"
    with values_file.open('w') as fp:
        json.dump(values, fp)
    logger.info("all data retrieved from simcore: %s", values_file)

async def upload_data(outputs_path):
    logger.info("uploading data to simcore...")
    PORTS = node_ports.ports()

    for port in PORTS.outputs:        
        logger.debug("uploading data to port '%s' with value '%s'...", port.key, port.value)
        if _FILE_TYPE_PREFIX in port.type:
            src_folder = outputs_path / port.key
            list_files = list(src_folder.glob("*"))
            if len(list_files) == 1:
                # special case, direct upload
                await port.set(list_files[0])
                continue
            # generic case let's create an archive
            temp_file = tempfile.NamedTemporaryFile(suffix=".tgz")
            temp_file.close()
            for _file in list_files:
                with tarfile.open(temp_file.name, mode='w:gz') as tar_ptr:
                    for file_path in list_files:
                        tar_ptr.add(file_path, arcname=file_path.name, recursive=False)
            await port.set(temp_file.name)
            Path(temp_file.name).unlink()
    logger.info("all data uploaded to simcore")

def _create_ports_sub_folders(ports: node_ports._items_list.ItemsList, parent_path: Path): # pylint: disable=protected-access
    for port in ports:
        if _FILE_TYPE_PREFIX in port.type:
            sub_folder = parent_path / port.key
            sub_folder.mkdir(exist_ok=True, parents=True)

class RetrieveHandler(IPythonHandler):

    def initialize(self):
        self.inputs_path = Path("~/inputs").expanduser()
        self.outputs_path = Path("~/outputs").expanduser()
        PORTS = node_ports.ports()
        _create_ports_sub_folders(PORTS.inputs, self.inputs_path)
        _create_ports_sub_folders(PORTS.outputs, self.outputs_path)
    
    async def get(self):
        try:
            await download_data(self.inputs_path)
            await upload_data(self.outputs_path)
            self.set_status(204)
        except node_ports.exceptions as exc:
            self.set_status(500, reason=exc.msg)
        finally:
            self.finish('completed retrieve!')
        
        

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
