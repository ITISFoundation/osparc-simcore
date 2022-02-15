import sqlalchemy as sa

from .base import metadata

study_folder = sa.Table(
    "study_folder",
    metadata,
    sa.Column(
        "study_id",
        sa.BigInteger,
        sa.ForeignKey("projects.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "folder_id",
        sa.BigInteger,
        sa.ForeignKey("folders.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.UniqueConstraint("study_id"),
)

folders = sa.Table(
    "folders",
    metadata,
    sa.Column("id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("description", sa.String, nullable=True),
    sa.Column("color", sa.String, nullable=False),
)
