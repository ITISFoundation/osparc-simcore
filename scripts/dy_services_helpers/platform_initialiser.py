import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

import tenacity
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from s3wrapper.s3_client import S3Client
from simcore_sdk import node_ports
from simcore_sdk.config.db import Config as db_config
from simcore_sdk.config.s3 import Config as s3_config
from simcore_sdk.models.pipeline_models import (Base, ComputationalPipeline,
                                                ComputationalTask)


class DbSettings:
    def __init__(self):
        self._db_config = db_config()
        self.db = create_engine(self._db_config.endpoint, client_encoding='utf8')
        self.Session = sessionmaker(self.db)
        self.session = self.Session()

class S3Settings:
    def __init__(self):
        self._config = s3_config()
        self.client = S3Client(endpoint=self._config.endpoint,
            access_key=self._config.access_key, secret_key=self._config.secret_key)
        self.bucket = self._config.bucket_name
        self.client.create_bucket(self.bucket)

@tenacity.retry(wait=tenacity.wait_fixed(2), stop=tenacity.stop_after_attempt(5) | tenacity.stop_after_delay(20))
def init_db():
    db = DbSettings()    
    Base.metadata.create_all(db.db)
    return db

@tenacity.retry(wait=tenacity.wait_fixed(2), stop=tenacity.stop_after_attempt(5) | tenacity.stop_after_delay(20))
def init_s3():
    s3 = S3Settings()
    return s3

async def _initialise_platform(port_configuration_path: Path, file_generator):
    
    
    with port_configuration_path.open() as file_pointer:
        configuration = json.load(file_pointer)
    
    if not all(k in configuration for k in ("schema", "inputs", "outputs")):
        raise Exception("invalid port configuration in {}, {}!".format(str(port_configuration_path), configuration))

    # init s3 to ensure we have a bucket
    init_s3()
    # set up db
    db = init_db()

    # create a new pipeline
    new_Pipeline = ComputationalPipeline()
    db.session.add(new_Pipeline)
    db.session.commit()

    # create a new node
    node_uuid = str(uuid.uuid4())
    # now create the node in the db with links to S3
    new_Node = ComputationalTask(project_id=new_Pipeline.project_id, 
                                node_id=node_uuid, 
                                schema=configuration["schema"], 
                                inputs=configuration["inputs"], 
                                outputs=configuration["outputs"])
    db.session.add(new_Node)
    db.session.commit()
    
    # set up node_ports
    node_ports.node_config.NODE_UUID = node_uuid
    PORTS = node_ports.ports()
    # push the file to the S3 for each input item
    file_index = 0
    for key, input_item in configuration["schema"]["inputs"].items():
        if str(input_item["type"]).startswith("data:"):
            file_to_upload = file_generator(file_index)
            if file_to_upload is not None:
                # upload to S3
                await PORTS.inputs[key].set(Path(file_to_upload))
                file_index += 1

    
    # print the node uuid so that it can be set as env variable from outside
    print("{pipelineid},{nodeuuid}".format(pipelineid=str(new_Node.project_id), nodeuuid=node_uuid))

def main(port_configuration_path: Path, file_generator):
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_initialise_platform(port_configuration_path, file_generator))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialise an oSparc database/S3 with user data for development.")
    parser.add_argument("portconfig", help="The path to the port configuration file (json format)", type=Path)
    group = parser.add_mutually_exclusive_group()    
    group.add_argument("--files", help="any number of files to upload", type=Path, nargs="*")
    group.add_argument("--folder", help="a path to upload files from", type=Path)
    args = sys.argv[1:]
    options = parser.parse_args(args)
    #print("options %s", options)
    if options.files is not None:
        def _file_generator(file_index: int):
            if file_index < len(options.files):
                return options.files[file_index]
            return None
        main(port_configuration_path=options.portconfig, file_generator=_file_generator)

    if options.folder is not None:
        def _file_generator(file_index: int):
            files = [x for x in options.folder.iterdir() if x.is_file()]
            if file_index < len(files):
                return files[file_index]
            return None
        main(port_configuration_path=options.portconfig, file_generator=_file_generator)    

    
