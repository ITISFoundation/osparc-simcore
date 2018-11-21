import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from platform_initialiser import main as init_platform


def _create_dummy_table(number_of_rows, number_of_columns):
    time = np.arange(number_of_rows).reshape(number_of_rows,1)
    matrix = np.random.randn(number_of_rows, number_of_columns)
    fullmatrix = np.hstack((time, matrix))
    df = pd.DataFrame(fullmatrix)
    return df

def main():
    parser = argparse.ArgumentParser(description="Initialise an oSparc database/S3 with fake data for development.")
    parser.add_argument("portconfig", help="The path to the port configuration file (json format)", type=Path)
    parser.add_argument("rows", help="The number of rows in each table", type=int)
    parser.add_argument("columns", help="The number of columns in each table", type=int)
    parser.add_argument("files", help="The number of tables in case of folder-url type", type=int)
    parser.add_argument("separator", help="The value separator to be used, for example tab or space or any single character", type=str)
    args = sys.argv[1:]
    options = parser.parse_args(args)
    if "tab" in options.separator:
        separator = "\t"
    elif "space" in options.separator:
        separator = " "
    else:
        separator = options.separator    
    

    def _file_generator(file_index: int): # pylint: disable=W0613
        # on Windows you need to close the file to be sure to re-open it to get a name
        temp_file = tempfile.NamedTemporaryFile(suffix=".csv")
        temp_file.close()
        df = _create_dummy_table(options.rows, options.columns)
        with open(temp_file.name, "w") as file_pointer:
            df.to_csv(path_or_buf=file_pointer, sep=separator, header=False, index=False)        
            return temp_file.name
        Path(temp_file.name).unlink()

    init_platform(port_configuration_path=options.portconfig, file_generator=_file_generator)

if __name__ == "__main__":
    main()
