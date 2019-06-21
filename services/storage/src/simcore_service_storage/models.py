""" Database models

"""
import datetime
import uuid
from pathlib import Path
from typing import Tuple

import attr
import sqlalchemy as sa

from simcore_service_storage.settings import (DATCORE_STR, SIMCORE_S3_ID,
                                              SIMCORE_S3_STR)

#FIXME: W0611:Unused UUID imported from sqlalchemy.dialects.postgresql
#from sqlalchemy.dialects.postgresql import UUID

#FIXME: R0902: Too many instance attributes (11/7) (too-many-instance-attributes)
#pylint: disable=R0902

metadata = sa.MetaData()

# File meta data
file_meta_data = sa.Table(
    "file_meta_data", metadata,
    sa.Column("file_uuid", sa.String, primary_key=True),
    sa.Column("location_id", sa.String),
    sa.Column("location", sa.String),
    sa.Column("bucket_name", sa.String),
    sa.Column("object_name", sa.String),
    sa.Column("project_id", sa.String),
    sa.Column("project_name", sa.String),
    sa.Column("node_id", sa.String),
    sa.Column("node_name", sa.String),
    sa.Column("file_name", sa.String),
    sa.Column("user_id", sa.String),
    sa.Column("user_name", sa.String),
    sa.Column("file_id", sa.String),
    sa.Column("raw_file_path", sa.String),
    sa.Column("display_file_path", sa.String),
    sa.Column("created_at", sa.String),
    sa.Column("last_modified", sa.String),
    sa.Column("file_size", sa.Integer)
#    sa.Column("state", sa.String())
)


def _parse_datcore(file_uuid: str) -> Tuple[str, str]:
    # we should have 12/123123123/111.txt

    object_name = "invalid"
    dataset_name = "invalid"

    parts = file_uuid.split("/")

    if len(parts) > 1:
        dataset_name = parts[0]
        object_name = "/".join(parts[1:])

    return dataset_name, object_name

def _locations():
    # TODO: so far this is hardcoded
    simcore_s3 = {
    "name" : SIMCORE_S3_STR,
    "id" : 0
    }
    datcore = {
    "name" : DATCORE_STR,
    "id"   : 1
    }
    return [simcore_s3, datcore]

def _location_from_id(location_id : str) ->str:
    # TODO create a map to sync _location_from_id and _location_from_str
    loc_str = "undefined"
    if location_id == "0":
        loc_str = SIMCORE_S3_STR
    elif location_id == "1":
        loc_str = DATCORE_STR

    return loc_str

def _location_from_str(location : str) ->str:
    intstr = "undefined"
    if location == SIMCORE_S3_STR:
        intstr = "0"
    elif location == DATCORE_STR:
        intstr = "1"

    return intstr


@attr.s(auto_attribs=True)
class FileMetaData:
    """ This is a proposal, probably no everything is needed.
        It is actually an overkill

        file_name       : display name for a file
        location_id     : storage location
        location_name   : storage location display name
        project_id      : project_id
        projec_name     : project display name
        node_id         : node id
        node_name       : display_name
        bucket_name     : name of the bucket
        object_name     : s3 object name = folder/folder/filename.ending
        user_id         : user_id
        user_name       : user_name

        file_uuid       : unique identifier for a file:

            bucket_name/project_id/node_id/file_name = /bucket_name/object_name


        state:  on of OK, UPLOADING, DELETED

        """
    file_uuid: str=""
    location_id: str=""
    location: str=""
    bucket_name: str=""
    object_name: str=""
    project_id: str=""
    project_name: str=""
    node_id: str=""
    node_name: str=""
    file_name: str=""
    user_id: str=""
    user_name: str=""

    # unique uuid for the file
    # simcore.s3: uuid created upon insertion
    # datcore: datcore uuid
    #
    file_id: str = "" # unique uuid for the file

    # raw path to file
    # simcore.s3: proj_id/node_id/filename.ending
    #             emailaddress/...
    # datcore: dataset/collection/filename.ending
    raw_file_path: str = ""
    # human readlable  path to file
    # simcore.s3: proj_name/node_name/filename.ending
    #              my_documents/...
    # datcore: dataset/collection/filename.ending
    display_file_path: str = "" # human readlable file path : , my_documents/folder/filename.ending,
    created_at: str = ""
    last_modified: str =""
    file_size: int = 0

    def simcore_from_uuid(self, file_uuid: str, bucket_name: str):
        parts = file_uuid.split("/")
        assert len(parts) == 3
        if len(parts) == 3:
            self.location = SIMCORE_S3_STR
            self.location_id = SIMCORE_S3_ID
            self.bucket_name = bucket_name
            self.object_name = "/".join(parts[:])
            self.file_name = parts[2]
            self.project_id = parts[0]
            self.node_id = parts[1]
            self.file_uuid = file_uuid
            self.file_id = str(uuid.uuid4())
            self.raw_file_path = self.file_uuid
            self.display_file_path = str(Path("not") / Path("yet") / Path("implemented"))
            self.created_at = str(datetime.datetime.now())
            self.last_modified = self.created_at
            self.file_size = -1

    def __str__(self):
        d = attr.asdict(self)
        _str =""
        for _d in d:
            _str += "  {0: <25}: {1}\n".format(_d, str(d[_d]))
        return _str
