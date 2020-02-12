""" Database models

"""
import datetime
from pathlib import Path
from typing import Tuple

import attr

from simcore_postgres_database.storage_models import (file_meta_data, metadata,
                                                      projects, tokens,
                                                      user_to_projects, users)
from simcore_service_storage.settings import (DATCORE_STR, SIMCORE_S3_ID,
                                              SIMCORE_S3_STR)

#FIXME: W0611:Unused UUID imported from sqlalchemy.dialects.postgresql
#from sqlalchemy.dialects.postgresql import UUID

#FIXME: R0902: Too many instance attributes (11/7) (too-many-instance-attributes)
#pylint: disable=R0902


def _parse_datcore(file_uuid: str) -> Tuple[str, str]:
    # we should have 12/123123123/111.txt and return (12/123123123, 111.txt)

    file_path = Path(file_uuid)
    destination = file_path.parent
    file_name = file_path.name

    return destination, file_name

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
class DatasetMetaData:
    dataset_id: str=""
    display_name: str=""

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

        file_id         : unique uuid for the file

            simcore.s3: uuid created upon insertion
            datcore: datcore uuid

        raw_file_path   : raw path to file

            simcore.s3: proj_id/node_id/filename.ending
            emailaddress/...
            datcore: dataset/collection/filename.ending

        display_file_path: human readlable  path to file

            simcore.s3: proj_name/node_name/filename.ending
            my_documents/...
            datcore: dataset/collection/filename.ending

        created_at          : time stamp
        last_modified       : time stamp
        file_size           : size in bytes

        TODO:
        state:  on of OK, UPLOADING, DELETED

        """
    #pylint: disable=attribute-defined-outside-init
    def simcore_from_uuid(self, file_uuid: str, bucket_name: str):
        parts = file_uuid.split("/")
        if len(parts) == 3:
            self.location = SIMCORE_S3_STR
            self.location_id = SIMCORE_S3_ID
            self.bucket_name = bucket_name
            self.object_name = "/".join(parts[:])
            self.file_name = parts[2]
            self.project_id = parts[0]
            self.node_id = parts[1]
            self.file_uuid = file_uuid
            self.file_id = file_uuid
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


attr.s(
    these={c.name:attr.ib(default=None) for c in file_meta_data.c},
    init=True,
    kw_only=True)(FileMetaData)


@attr.s(auto_attribs=True)
class FileMetaDataEx():
    """Extend the base type by some additional attributes that shall not end up in the db
    """
    fmd: FileMetaData
    parent_id: str=""

    def __str__(self):
        _str = str(self.fmd)
        _str += "  {0: <25}: {1}\n".format("parent_id", str(self.parent_id))
        return _str


__all__ = [
    "file_meta_data",
    "tokens",
    "metadata",
    "FileMetaData",
    "FileMetaDataEx",
    "projects",
    "users",
    "user_to_projects"
]
