import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


metadata = sa.MetaData()

# File meta data
file_meta_data = sa.Table(
    "file_meta_data", metadata,
    sa.Column("object_name", sa.String, primary_key=True),
    sa.Column("bucket_name", sa.String),
    sa.Column("file_id", sa.String), #uuid
    sa.Column("file_name", sa.String),
    sa.Column("user_id", sa.Integer),
    sa.Column("user_name", sa.String),
    sa.Column("location", sa.String),
    sa.Column("project_id", sa.Integer),
    sa.Column("project_name", sa.String),
    sa.Column("node_id", sa.Integer),
    sa.Column("node_name", sa.String),
)

class FileMetaData:
    """ This is a proposal, probably no everything is needed.


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

    def __init__(self, object_name: str, bucket_name ="", file_id: str="", file_name: str="", user_id: int=-1, user_name: str="", location: str="", project_id: int=-1,
            project_name: str="", node_id: int=-1, node_name: str="", **kargs):
        
        self.object_name = object_name
        self.bucket_name = bucket_name
        self.file_id = file_id
        self.file_name = file_name
        self.user_id = user_id
        self.user_name =user_name
        self.location = location
        self.project_id = project_id
        self.project_name = project_name
        self.node_id = node_id
        self.node_name = node_name


