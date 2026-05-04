from models_library.functions import (
    FunctionAccessRightsDB,
    FunctionJobAccessRightsDB,
    FunctionJobCollectionAccessRightsDB,
    RegisteredFunctionDB,
    RegisteredFunctionJobCollectionDB,
    RegisteredFunctionJobDB,
)
from simcore_postgres_database.models.funcapi_function_job_collections_access_rights_table import (
    function_job_collections_access_rights_table,
)
from simcore_postgres_database.models.funcapi_function_job_collections_table import (
    function_job_collections_table,
)
from simcore_postgres_database.models.funcapi_function_jobs_access_rights_table import (
    function_jobs_access_rights_table,
)
from simcore_postgres_database.models.funcapi_function_jobs_table import (
    function_jobs_table,
)
from simcore_postgres_database.models.funcapi_functions_access_rights_table import (
    functions_access_rights_table,
)
from simcore_postgres_database.models.funcapi_functions_table import functions_table
from simcore_postgres_database.utils_repos import get_columns_from_db_model

_FUNCTIONS_TABLE_COLS = get_columns_from_db_model(functions_table, RegisteredFunctionDB)

_FUNCTION_JOBS_TABLE_COLS = get_columns_from_db_model(function_jobs_table, RegisteredFunctionJobDB)
_FUNCTION_JOB_COLLECTIONS_TABLE_COLS = get_columns_from_db_model(
    function_job_collections_table, RegisteredFunctionJobCollectionDB
)
_FUNCTIONS_ACCESS_RIGHTS_TABLE_COLS = get_columns_from_db_model(functions_access_rights_table, FunctionAccessRightsDB)
_FUNCTION_JOBS_ACCESS_RIGHTS_TABLE_COLS = get_columns_from_db_model(
    function_jobs_access_rights_table, FunctionJobAccessRightsDB
)
_FUNCTION_JOB_COLLECTIONS_ACCESS_RIGHTS_TABLE_COLS = get_columns_from_db_model(
    function_job_collections_access_rights_table, FunctionJobCollectionAccessRightsDB
)
