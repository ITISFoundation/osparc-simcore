import logging
import os
from pathlib import Path

from notebook.base.handlers import IPythonHandler
from notebook.utils import url_path_join

from simcore_sdk.node_ports import exceptions
from simcore_sdk.node_data import data_manager

log = logging.getLogger(__name__)

_STATE_PATH = os.environ.get("SIMCORE_NODE_APP_STATE_PATH", "undefined")

def _state_path() -> Path:
    assert _STATE_PATH != "undefined", "SIMCORE_NODE_APP_STATE_PATH is not defined!"
    state_path = Path(_STATE_PATH)
    return state_path

class StateHandler(IPythonHandler):
    def initialize(self): #pylint: disable=no-self-use
        pass

    async def post(self):
        log.info("started pushing current state to S3...")
        try:
            await data_manager.push(_state_path())
            self.set_status(204)
        except exceptions.NodeportsException as exc:
            log.exception("Unexpected error while pushing state")
            self.set_status(500, reason=str(exc))
        finally:
            self.finish()

    async def get(self):
        log.info("started pulling state to S3...")
        try:
            await data_manager.pull(_state_path())
            self.set_status(204)
        except exceptions.S3InvalidPathError as exc:
            log.exception("Invalid path to S3 while retrieving state")
            self.set_status(404, reason=str(exc))
        except exceptions.NodeportsException as exc:
            log.exception("Unexpected error while retrieving state")
            self.set_status(500, reason=str(exc))
        finally:
            self.finish('completed pulling state')



def load_jupyter_server_extension(nb_server_app):
    """ Called when the extension is loaded

    - Adds API to server

    :param nb_server_app: handle to the Notebook webserver instance.
    :type nb_server_app: NotebookWebApplication
    """
    web_app = nb_server_app.web_app
    host_pattern = '.*$'
    route_pattern = url_path_join(web_app.settings['base_url'], '/state')

    web_app.add_handlers(host_pattern, [(route_pattern, StateHandler)])
