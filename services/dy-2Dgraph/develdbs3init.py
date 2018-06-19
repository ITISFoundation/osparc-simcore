import os
import tempfile
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

def create_dummy():
    inputs = [
        dict(
            key="in_1",
            label="computational data",
            description="these are computed data out of a pipeline",
            type="file-url",
            value="/home/jovyan/data/outputControllerOut.dat",
            timestamp="2018-05-23T15:34:53.511Z"
        ),
        dict(
            key="in_5",
            label="some number",
            description="numbering things",
            type="int",
            value="666",
            timestamp="2018-05-23T15:34:53.511Z"
        )
        ]
    outputs = [
        dict(
            key="out_1",
            label="some output",
            description="this is a special dummy output",
            type="itn",
            value="null",
            timestamp="2018-05-23T15:34:53.511Z"
        )
    ]
    # initialise db
    db = DbSettings()
    Base.metadata.create_all(db.db)
    node_uuid = os.environ.get('SIMCORE_NODE_UUID')
    new_Pipeline = ComputationalPipeline()
    db.session.add(new_Pipeline)
    db.session.commit()
    new_Node = ComputationalTask(pipeline_id=new_Pipeline.pipeline_id, node_id=node_uuid, input=inputs, output=outputs)
    
    db.session.add(new_Node)
    db.session.commit()

    # create a dummy file
    temp_file = tempfile.NamedTemporaryFile()
    temp_file.close()
    with open(temp_file.name, "w") as file_pointer:
        file_pointer.write("This is a nice dummy data here")
    
    s3_object_name = Path(str(new_Pipeline.pipeline_id), node_uuid, inputs[0]["key"])

    # initialise s3
    s3 = S3Settings()
    s3.client.upload_file(s3.bucket, s3_object_name.as_posix(), temp_file.name)
    Path(temp_file.name).unlink()

#create_dummy()