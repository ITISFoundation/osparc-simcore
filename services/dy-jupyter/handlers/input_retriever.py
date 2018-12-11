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


_INPUTS_FOLDER = "~/inputs"
_OUTPUTS_FOLDER = "~/outputs"
_FILE_TYPE_PREFIX = "data:"
_KEY_VALUE_FILE_NAME = "key_values.json"

async def download_data():
    logger.info("retrieving data from simcore...")
    PORTS = node_ports.ports()
    inputs_path = Path(_INPUTS_FOLDER).expanduser()
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

    values_file = inputs_path / _KEY_VALUE_FILE_NAME
    values_file.write_text(json.dumps(values))
    logger.info("all data retrieved from simcore: %s", values)

async def upload_data():
    logger.info("uploading data to simcore...")
    PORTS = node_ports.ports()
    outputs_path = Path(_OUTPUTS_FOLDER).expanduser()
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
        else:
            values_file = outputs_path / _KEY_VALUE_FILE_NAME
            if values_file.exists():
                values = json.loads(values_file.read_text())
                if port.key in values:
                    port.set(values[port.key])

    logger.info("all data uploaded to simcore")

class RetrieveHandler(IPythonHandler):
    async def get(self):
        try:
            await download_data()
            await upload_data()
            self.set_status(204)
        except node_ports.exceptions.NodeportsException as exc:
            self.set_status(500, reason=str(exc))
        finally:
            self.finish('completed retrieve!')

def _create_ports_sub_folders(ports: node_ports._items_list.ItemsList, parent_path: Path): # pylint: disable=protected-access    
    values = {}
    for port in ports:
        values[port.key] = port.value
        if _FILE_TYPE_PREFIX in port.type:
            sub_folder = parent_path / port.key
            sub_folder.mkdir(exist_ok=True, parents=True)
    
    parent_path.mkdir(exist_ok=True, parents=True)    
    values_file = parent_path / _KEY_VALUE_FILE_NAME
    values_file.write_text(json.dumps(values))

def _init_sub_folders():
    inputs_path = Path(_INPUTS_FOLDER).expanduser()
    outputs_path = Path(_OUTPUTS_FOLDER).expanduser()
    PORTS = node_ports.ports()
    _create_ports_sub_folders(PORTS.inputs, inputs_path)
    _create_ports_sub_folders(PORTS.outputs, outputs_path)
        
        

def load_jupyter_server_extension(nb_server_app):
    """
    Called when the extension is loaded.

    Args:
        nb_server_app (NotebookWebApplication): handle to the Notebook webserver instance.
    """
    _init_sub_folders()

    web_app = nb_server_app.web_app
    host_pattern = '.*$'
    route_pattern = url_path_join(web_app.settings['base_url'], '/retrieve')
    
    web_app.add_handlers(host_pattern, [(route_pattern, RetrieveHandler)])
