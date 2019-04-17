import logging
from pathlib import Path

from notebook.base.handlers import IPythonHandler
from notebook.utils import url_path_join

import state_manager

log = logging.getLogger(__name__)


_NOTEBOOKS_FOLDER = Path("~/notebooks").expanduser()

class StateHandler(IPythonHandler):
    def initialize(self): #pylint: disable=no-self-use
        pass

    async def post(self):
        log.info("started pushing current state to S3...")
        await state_manager.push(_NOTEBOOKS_FOLDER)
        self.set_status(200)
        self.finish('completed pushing state')

    async def get(self):
        log.info("started pulling state to S3...")
        self.set_status(200)
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
