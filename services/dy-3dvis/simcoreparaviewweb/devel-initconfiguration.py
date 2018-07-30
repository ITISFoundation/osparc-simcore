import json
import sys
import uuid
from pathlib import Path

import tenacity
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from s3wrapper.s3_client import S3Client
from simcore_sdk.config.db import Config as db_config
from simcore_sdk.config.s3 import Config as s3_config
from simcore_sdk.models.pipeline_models import (Base, ComputationalPipeline,
                                                ComputationalTask)

#TODO: use env variable here
TEST_DATA_PATH = Path(r"/home/root/test-data")

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

def create_dummy(json_configuration_file_path):
    with open(json_configuration_file_path) as file_pointer:
        json_configuration = file_pointer.read()
    
    db = init_db()
    new_Pipeline = ComputationalPipeline()
    db.session.add(new_Pipeline)
    db.session.commit()

    node_uuid = str(uuid.uuid4())
    # correct configuration with node uuid
    json_configuration = json_configuration.replace("SIMCORE_NODE_UUID", node_uuid)
    configuration = json.loads(json_configuration)
    

    # init s3
    s3 = init_s3()

    uploaded_files = []
    # push the file to the S3 for each input item
    for input_item in configuration["inputs"]:
        available_files = [x for x in TEST_DATA_PATH.iterdir() if x.is_file() and x not in uploaded_files]
        if not available_files:
            # it could be correct so just stop here
            break
        if input_item["type"] == "file-url":
            filename = available_files[0].name
            s3_object_name = Path(str(new_Pipeline.pipeline_id), node_uuid, str(filename))
            s3.client.upload_file(s3.bucket, s3_object_name.as_posix(), str(available_files[0]))
            input_item["key"] = str(filename)  
            input_item["value"] = ".".join(["link", node_uuid, str(filename)])  
            uploaded_files.append(available_files[0])
        elif input_item["type"] == "folder-url":
            for f in available_files:
                #i = available_files.index(f)
                s3_object_name = Path(str(new_Pipeline.pipeline_id), node_uuid, input_item["key"], str(filename))
                #configuration["inputs"]["key"] = input_item["key"]
                s3.client.upload_file(s3.bucket, s3_object_name.as_posix(), f)


    # now create the node in the db with links to S3
    new_Node = ComputationalTask(pipeline_id=new_Pipeline.pipeline_id, node_id=node_uuid, input=configuration["inputs"], output=configuration["outputs"])
    db.session.add(new_Node)
    db.session.commit()

    # print the node uuid so that it can be set as env variable from outside
    print(node_uuid)

if __name__ == "__main__":    
    create_dummy(sys.argv[1])
