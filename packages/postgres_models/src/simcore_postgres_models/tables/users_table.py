# TODO: services/web/server/src/simcore_service_webserver/db_models.py

users = sa.Table("users", metadata,
    sa.Column("id", sa.BigInteger, nullable=False),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("email", sa.String, nullable=False),
    sa.Column("password_hash", sa.String, nullable=False),
    sa.Column("status",
        sa.Enum(UserStatus),
        nullable=False,
        default=UserStatus.CONFIRMATION_PENDING),
    sa.Column("role",
        sa.Enum(UserRole),
        nullable=False,
        default=UserRole.USER),
    sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow),
    sa.Column("created_ip", sa.String(), nullable=True),

    #
    sa.PrimaryKeyConstraint("id", name="user_pkey"),
    sa.UniqueConstraint("email", name="user_login_key"),
)
