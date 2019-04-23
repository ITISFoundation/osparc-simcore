import asyncio
import logging
import os
from pathlib import Path
from simcore_sdk.node_data import data_manager

log = logging.getLogger(__file__ if __name__ == "__main__" else __name__)

def export_to_osparc_hook(model, os_path, contents_manager): # pylint: disable=unused-argument
    """export the notebooks to oSparc S3 when notebooks get saved
    """

    if model['type'] != 'notebook':
        return

    notebooks_path = Path(os.environ.get("SIMCORE_NODE_APP_STATE_PATH", "undefined"))
    asyncio.ensure_future(data_manager.push(notebooks_path))
