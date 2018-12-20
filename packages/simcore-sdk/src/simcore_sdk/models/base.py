from sqlalchemy.ext.declarative import declarative_base

# TODO: avoid inheriting from Base. Use instead explicit table definitions
# See https://docs.sqlalchemy.org/en/latest/orm/mapping_styles.html#classical-mappings
Base = declarative_base()

metadata = Base.metadata
