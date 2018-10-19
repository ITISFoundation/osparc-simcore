import argparse
import json
import sys
import tempfile
import uuid
from pathlib import Path

import tenacity
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import numpy as np
import pandas as pd
from s3wrapper.s3_client import S3Client
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

def create_dummy_table(number_of_rows, number_of_columns):
    time = np.arange(number_of_rows).reshape(number_of_rows,1)
    matrix = np.random.randn(number_of_rows, number_of_columns)
    fullmatrix = np.hstack((time, matrix))
    df = pd.DataFrame(fullmatrix)
    return df

def create_dummy(json_configuration_file_path: Path, number_of_rows: int, number_of_columns: int, number_of_files: int, sep: str ="\t"):
    with json_configuration_file_path.open() as file_pointer:
        json_configuration = file_pointer.read()
    
    # set up db
    db = init_db()
    new_Pipeline = ComputationalPipeline()
    db.session.add(new_Pipeline)
    db.session.commit()

    node_uuid = str(uuid.uuid4())
    # correct configuration with node uuid
    json_configuration = json_configuration.replace("SIMCORE_NODE_UUID", node_uuid)
    configuration = json.loads(json_configuration)
        

    # create a dummy table    
    s3 = init_s3()
    # push the file to the S3 for each input item
    for input_item in configuration["inputs"]:
        if input_item["type"] == "file-url" or input_item["type"] == "folder-url":
            # create a dummy file filled with dummy data
            temp_file = tempfile.NamedTemporaryFile(suffix=".csv")
            temp_file.close()
            # create dummy file containing a table
            df = create_dummy_table(number_of_rows, number_of_columns)
            with open(temp_file.name, "w") as file_pointer:
                df.to_csv(path_or_buf=file_pointer, sep=sep, header=False, index=False)        

        # upload to S3
        if input_item["type"] == "file-url":
            s3_object_name = Path(str(new_Pipeline.pipeline_id), node_uuid, Path(temp_file.name).name)
            s3.client.upload_file(s3.bucket, s3_object_name.as_posix(), temp_file.name)
        elif input_item["type"] == "folder-url":
            for i in range(number_of_files):
                s3_object_name = Path(str(new_Pipeline.pipeline_id), node_uuid, Path(temp_file.name).parent.name, str(i) + ".dat")
                s3.client.upload_file(s3.bucket, s3_object_name.as_posix(), temp_file.name)
        # update configuration
        if "FILENAME_ID" in input_item["value"]:
            input_item["value"] = input_item["value"].replace("FILENAME_ID", Path(temp_file.name).name)
        if "FOLDER_NAME_ID" in input_item["value"]:
            input_item["value"] = input_item["value"].replace("FOLDER_NAME_ID", Path(temp_file.name).parent.name)

    Path(temp_file.name).unlink()

    # now create the node in the db with links to S3
    new_Node = ComputationalTask(pipeline_id=new_Pipeline.pipeline_id, node_id=node_uuid, input=configuration["inputs"], output=configuration["outputs"])
    db.session.add(new_Node)
    db.session.commit()

    # print the node uuid so that it can be set as env variable from outside
    print(node_uuid)


parser = argparse.ArgumentParser(description="Initialise an oSparc database/S3 with fake data for development.")
parser.add_argument("portconfig", help="The path to the port configuration file (json format)", type=Path)
parser.add_argument("rows", help="The number of rows in each table", type=int)
parser.add_argument("columns", help="The number of columns in each table", type=int)
parser.add_argument("files", help="The number of tables in case of folder-url type", type=int)
parser.add_argument("separator", help="The value separator to be used, for example tab or space or any single character", type=str)
args = sys.argv[1:]
options = parser.parse_args(args)
if "tab" in options.separator:
    separator = "\t"
elif "space" in options.separator:
    separator = " "
else:
    separator = options.separator
create_dummy(options.portconfig, 
    number_of_rows=options.rows, 
    number_of_columns=options.columns, 
    number_of_files=options.files, 
    sep=separator)
