import sqlalchemy as sa

from .base import metadata

file_meta_data = sa.Table(
    "file_meta_data",
    metadata,
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
