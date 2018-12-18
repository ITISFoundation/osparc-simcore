import json
import logging
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

from notebook.base.handlers import IPythonHandler
from notebook.utils import url_path_join
from simcore_sdk import node_ports

logger = logging.getLogger(__name__)


_INPUTS_FOLDER = "~/inputs"
_OUTPUTS_FOLDER = "~/outputs"
_FILE_TYPE_PREFIX = "data:"
_KEY_VALUE_FILE_NAME = "key_values.json"

def _compress_files_in_folder(folder: Path, one_file_not_compress: bool = True) -> Path:
    list_files = list(folder.glob("*"))

    if list_files is None:
        return None

    if one_file_not_compress and len(list_files) == 1:
        return list_files[0]

    temp_file = tempfile.NamedTemporaryFile(suffix=".tgz")
    temp_file.close()
    for _file in list_files:
        with tarfile.open(temp_file.name, mode='w:gz') as tar_ptr:
            for file_path in list_files:
                tar_ptr.add(file_path, arcname=file_path.name, recursive=False)
    return Path(temp_file.name)

def _no_relative_path_tar(members: tarfile.TarFile):
    for tarinfo in members:
        path = Path(tarinfo.name)
        if path.is_absolute():
            # absolute path are not allowed
            continue
        if path.match("/../"):
            # relative paths are not allowed
            continue
        yield tarinfo

def _no_relative_path_zip(members: zipfile.ZipFile):
    for zipinfo in members.infolist():
        path = Path(zipinfo.filename)
        if path.is_absolute():
            # absolute path are not allowed
            continue
        if path.match("/../"):
            # relative paths are not allowed
            continue
        yield zipinfo

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
            dest_path = inputs_path / port.key
            dest_path.mkdir(exist_ok=True, parents=True)
            values[port.key] = {"key": port.key, "value": str(dest_path)}

            # clean up destination directory
            for path in dest_path.iterdir():
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
            # check if value is a compressed file
            if tarfile.is_tarfile(value):
                with tarfile.open(value) as tar_file:
                    tar_file.extractall(dest_path, members=_no_relative_path_tar(tar_file))
            elif zipfile.is_zipfile(value):
                with zipfile.ZipFile(value) as zip_file:
                    zip_file.extractall(dest_path, members=_no_relative_path_zip(zip_file))
            else:
                dest_path = dest_path / Path(value).name
                shutil.move(value, dest_path)

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
            if len(list_files) > 1:
                temp_file = tempfile.NamedTemporaryFile(suffix=".tgz")
                temp_file.close()
                for _file in list_files:
                    with tarfile.open(temp_file.name, mode='w:gz') as tar_ptr:
                        for file_path in list_files:
                            tar_ptr.add(file_path, arcname=file_path.name, recursive=False)
                try:
                    await port.set(temp_file.name)
                finally:
                    #clean up
                    Path(temp_file.name).unlink()
        else:
            values_file = outputs_path / _KEY_VALUE_FILE_NAME
            if values_file.exists():
                values = json.loads(values_file.read_text())
                if port.key in values and values[port.key] is not None:
                    await port.set(values[port.key])

    logger.info("all data uploaded to simcore")

class RetrieveHandler(IPythonHandler):
    def initialize(self): #pylint: disable=no-self-use
        PORTS = node_ports.ports()
        _create_ports_sub_folders(PORTS.inputs, Path(_INPUTS_FOLDER).expanduser())
        _create_ports_sub_folders(PORTS.outputs, Path(_OUTPUTS_FOLDER).expanduser())

    async def get(self):
        try:
            await download_data()
            await upload_data()
            self.set_status(200)
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
    Path(_INPUTS_FOLDER).expanduser().mkdir(exist_ok=True, parents=True)
    Path(_OUTPUTS_FOLDER).expanduser().mkdir(exist_ok=True, parents=True)



def load_jupyter_server_extension(nb_server_app):
    """ Called when the extension is loaded

    - Adds API to server

    :param nb_server_app: handle to the Notebook webserver instance.
    :type nb_server_app: NotebookWebApplication
    """
    _init_sub_folders()

    web_app = nb_server_app.web_app
    host_pattern = '.*$'
    route_pattern = url_path_join(web_app.settings['base_url'], '/retrieve')

    web_app.add_handlers(host_pattern, [(route_pattern, RetrieveHandler)])
