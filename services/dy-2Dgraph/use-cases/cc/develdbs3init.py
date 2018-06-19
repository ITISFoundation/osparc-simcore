import os
import sys
import tempfile
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from simcore_sdk.models.pipeline_models import Base, ComputationalTask, ComputationalPipeline
from simcore_sdk.config.db import Config as db_config

from simcore_sdk.config.s3 import Config as s3_config
from s3wrapper.s3_client import S3Client


class DbSettings(object):
    def __init__(self):
        self._db_config = db_config()
        self.db = create_engine(self._db_config.endpoint, client_encoding='utf8')
        self.Session = sessionmaker(self.db)
        self.session = self.Session()

class S3Settings(object):
    def __init__(self):
        self._config = s3_config()
        self.client = S3Client(endpoint=self._config.endpoint,
            access_key=self._config.access_key, secret_key=self._config.secret_key)
        self.bucket = self._config.bucket_name
        self.client.create_bucket(self.bucket)

def create_dummy(json_configuration_file_path):
    with open(Path("/home/jovyan", json_configuration_file_path)) as file_pointer:
        configuration = json.load(file_pointer)
    
    
    # initialise db
    db = DbSettings()
    Base.metadata.create_all(db.db)
    node_uuid = os.environ.get('SIMCORE_NODE_UUID')
    new_Pipeline = ComputationalPipeline()
    db.session.add(new_Pipeline)
    db.session.commit()
    os.environ["SIMCORE_PIPELINE_ID"] = str(new_Pipeline.pipeline_id) # set the env variable in the docker
    new_Node = ComputationalTask(pipeline_id=new_Pipeline.pipeline_id, node_id=node_uuid, input=configuration["inputs"], output=configuration["outputs"])
    
    db.session.add(new_Node)
    db.session.commit()

    # create a dummy file
    temp_file = tempfile.NamedTemporaryFile()
    temp_file.close()
    with open(temp_file.name, "w") as file_pointer:
        file_pointer.write("This is a nice dummy data here")
    
    # initialise s3
    s3 = S3Settings()
    for input_item in configuration["inputs"]:
        s3_object_name = Path(str(new_Pipeline.pipeline_id), node_uuid, input_item["key"])
        s3.client.upload_file(s3.bucket, s3_object_name.as_posix(), temp_file.name)
    Path(temp_file.name).unlink()

    print(new_Pipeline.pipeline_id)

if __name__ == "__main__":    
    create_dummy(sys.argv[1])