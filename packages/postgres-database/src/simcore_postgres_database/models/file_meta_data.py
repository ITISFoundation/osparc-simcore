import sqlalchemy as sa

from .base import metadata

file_meta_data = sa.Table(
    "file_meta_data",
    metadata,
    sa.Column("location_id", sa.String()),
    sa.Column("location", sa.String()),
    sa.Column("bucket_name", sa.String()),
    sa.Column("object_name", sa.String()),
    sa.Column("project_id", sa.String()),
    sa.Column("node_id", sa.String()),
    sa.Column("user_id", sa.String()),
    sa.Column("file_id", sa.String(), primary_key=True),
    sa.Column("created_at", sa.String()),
    sa.Column("last_modified", sa.String()),
    sa.Column("file_size", sa.BigInteger()),
    sa.Column(
        "entity_tag",
        sa.String(),
        nullable=True,
        doc="Entity tag (or ETag), represents a specific version of the object"
        "SEE https://docs.aws.amazon.com/AmazonS3/latest/API/RESTCommonResponseHeaders.html",
    ),
    sa.Column(
        "is_soft_link",
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
        doc="If true, this file is a soft link."
        "i.e. is another entry with the same object_name",
    ),
    sa.Column(
        "upload_id",
        sa.String(),
        nullable=True,
        doc="if filled, contains the uploadId for S3 multipart file upload",
    ),
    sa.Column(
        "upload_expires_at", sa.DateTime(), nullable=True, doc="Timestamp of expiration"
    ),
    sa.Column(
        "is_directory",
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
        doc="Set True when file_id is a directory",
    ),
)
