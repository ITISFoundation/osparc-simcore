import json
import logging
from contextlib import contextmanager

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import exc, sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from simcore_sdk.config.db import Config as db_config
from simcore_sdk.models.pipeline_models import ComputationalTask as NodeModel

from . import config

log = logging.getLogger(__name__)


@contextmanager
def session_scope(session_factory):
    """Provide a transactional scope around a series of operations

    """
    session = session_factory()
    try:
        yield session
    except:
        session.rollback()
        raise
    finally:
        session.close()

class DbSettings:
    def __init__(self):
        self._db_settings_config = db_config()
        self.db = create_engine(self._db_settings_config.endpoint, client_encoding='utf8')
        self.Session = sessionmaker(self.db)
        # self.session = self.Session()

class _NodeModelEncoder(json.JSONEncoder):
    def default(self, o): # pylint: disable=E0202
        log.debug("Encoding object: %s", o)
        if isinstance(o, NodeModel):
            log.debug("Encoding Node object")
            return {
                    "version": "0.1",
                    "schema": o.schema,
                    "inputs": o.inputs,
                    "outputs": o.outputs
                    }

        log.debug("Encoding object using defaults")
        return json.JSONEncoder.default(self, o)

def _get_node_from_db(node_uuid: str, session: sqlalchemy.orm.session.Session) -> NodeModel:
    log.debug("Reading from database for node uuid %s", node_uuid)
    try:
        return session.query(NodeModel).filter(NodeModel.node_id == node_uuid).one()
    except exc.NoResultFound:
        log.exception("the node id %s was not found", node_uuid)
    except exc.MultipleResultsFound:
        log.exception("the node id %s is not unique", node_uuid)

class DBManager:
    def __init__(self):
        self._db_settings = DbSettings()
        with session_scope(self._db_settings.Session) as session:
            node = session.query(NodeModel).filter(NodeModel.node_id == config.NODE_UUID).one()
            config.PROJECT_ID = node.project_id

    def write_ports_configuration(self, json_configuration: str, node_uuid: str):
        log.debug("Writing ports configuration")
        log.debug("Writing to database")

        node_configuration = json.loads(json_configuration)
        with session_scope(self._db_settings.Session) as session:
            updated_node = NodeModel(schema=node_configuration["schema"], inputs=node_configuration["inputs"], outputs=node_configuration["outputs"])
            node = _get_node_from_db(node_uuid=node_uuid, session=session)

            if node.schema != updated_node.schema:
                node.schema = updated_node.schema
                flag_modified(node, "schema")
            if node.inputs != updated_node.inputs:
                node.inputs = updated_node.inputs
                flag_modified(node, "inputs")
            if node.outputs != updated_node.outputs:
                node.outputs = updated_node.outputs
                flag_modified(node, "outputs")

            session.commit()

    def get_ports_configuration_from_node_uuid(self, node_uuid:str) -> str:
        log.debug("Getting ports configuration of node %s", node_uuid)
        log.debug("Reading from database")
        with session_scope(self._db_settings.Session) as session:
            node = _get_node_from_db(node_uuid, session)
            node_json_config = json.dumps(node, cls=_NodeModelEncoder)
        log.debug("Found and converted to json")
        return node_json_config
