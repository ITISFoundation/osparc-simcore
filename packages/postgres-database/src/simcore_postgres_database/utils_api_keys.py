import sqlalchemy as sa


def hash_secret(secret: str) -> sa.sql.ClauseElement:
    return sa.func.crypt(secret, sa.func.gen_salt("bf", 10))
