""" Database models

"""
from typing import Tuple

import attr
import sqlalchemy as sa

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
    sa.Column("file_id", sa.String),
    sa.Column("file_name", sa.String),
    sa.Column("user_id", sa.String),
    sa.Column("user_name", sa.String),
)


def _parse_simcore(file_uuid: str) -> Tuple[str, str]:
    # we should have simcore.s3/simcore/12/123123123/111.txt

    object_name = "invalid"
    bucket_name = "invalid"

    parts = file_uuid.split("/")

    if len(parts) > 2:
        bucket_name = parts[1]
        object_name = "/".join(parts[2:])

    return bucket_name, object_name

def _parse_datcore(file_uuid: str) -> Tuple[str, str]:
    # we should have datcore/boom/12/123123123/111.txt
    return _parse_simcore(file_uuid)

def _locations():
    # TODO: so far this is hardcoded
    simcore_s3 = {
    "name" : "simcore.s3",
    "id" : 0
    }
    datcore = {
    "name" : "datcore",
    "id"   : 1
    }
    return [simcore_s3, datcore]

def _location_from_id(location_id : str) ->str:
    if location_id == "0":
        return "simcore.s3"
    elif location_id == "1":
        return "datcore"

def _location_from_str(location : str) ->str:
    if location == "simcore.s3":
        return "0"
    elif location == "datcore":
        return "1"


@attr.s(auto_attribs=True)
class FileMetaData:
    """ This is a proposal, probably no everything is needed.
        It is actually an overkill

        for simcore.s3:
            bucket_name = "simcore", probably fixed
            object_name = proj_id/node_id/file_name ? can also be a uuid because we still have the filename?
            file_id = unique identifier
            file_name = the acutal filename (this may be different from what we store in s3)
            user_id = unique id of the owner of the file --> maps to the user database
            user_name = name of the owner
            location = "simcore.s3" for now, there might be more to come
            project_id = the project that owns this file --> might become a list
            project_name = name of the poject --> userful for frontend to display folders
            node_id = the node_id within the project, again, might be a list?
            node_name = the name of the node (might be useful for searching previously used files given the name of a service)

        for datcore:
            bucket_name = dataset_name
            object_name = filename (including potentially a collection if they still support that)
            file_name = filename

            # dat core allows to attach metadata to files --> see datcore.py

        """
    #pylint: disable=W0613
    file_uuid: str=""
    location_id: str=""
    location: str=""
    bucket_name: str=""
    object_name: str=""
    project_id: str=""
    project_name: str=""
    node_id: str=""
    node_name: str=""
    file_id: str=""
    file_name: str=""
    user_id: str=""
    user_name: str=""

    def simcore_from_uuid(self, file_uuid: str):
        parts = file_uuid.split("/")
        assert len(parts) > 3
        if len(parts) > 3:
            self.location = parts[0]
            self.location_id = _location_from_str(self.location)
            self.bucket_name = parts[1]
            self.object_name = "/".join(parts[2:])
            self.file_name = parts[-1]
            self.file_id = parts[-1]
            self.project_id = parts[2]
            self.node_id = parts[3]
