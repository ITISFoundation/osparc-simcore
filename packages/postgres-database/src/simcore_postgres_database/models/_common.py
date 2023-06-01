import sqlalchemy as sa


def column_created_datetime(timezone: bool = True) -> sa.Column:
    return sa.Column(
        "created",
        sa.DateTime(timezone=timezone),
        nullable=False,
        server_default=sa.sql.func.now(),
        doc="Timestamp auto-generated upon creation",
    )


def column_modified_datetime(timezone: bool = True) -> sa.Column:
    return sa.Column(
        "modified",
        sa.DateTime(timezone=timezone),
        nullable=False,
        server_default=sa.sql.func.now(),
        onupdate=sa.sql.func.now(),
        doc="Timestamp with last row update",
    )
