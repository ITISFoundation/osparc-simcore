import sqlalchemy as sa

from .base import metadata

study_tags = sa.Table("study_tags", metadata,
    sa.Column("study_id", sa.BigInteger,
        sa.ForeignKey("projects.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False
    ),
    sa.Column("tag_id", sa.BigInteger,
        sa.ForeignKey("tags.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False
    )
)

tags = sa.Table("tags", metadata,
    sa.Column("id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("user_id", sa.BigInteger,
        sa.ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("description", sa.String, nullable=True),
    sa.Column("color", sa.String, nullable=False)
)
