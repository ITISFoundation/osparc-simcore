# TODO: services/web/server/src/simcore_service_webserver/db_models.py


# NOTE: this is another way of of defining keys ...
tokens = sa.Table("tokens", metadata,
    sa.Column("token_id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("user_id", sa.BigInteger, sa.ForeignKey(users.c.id), nullable=False),
    sa.Column("token_service", sa.String, nullable=False),
    sa.Column("token_data", sa.JSON, nullable=False),

)
