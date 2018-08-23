#/bin/bash
cd $(dirname $0)
usage()
{
    echo "usage: openapi_python_server_codegen [[[-i input] [-o output directory]] | [-h help]]"
}

input_file= 
output_directory= 
generator="python-flask"
# process arguments
while [ "$1" != "" ]; do
    case $1 in
        -i | --input )          shift
                                input_file=$1
                                ;;
        -o | --outdir )         shift
                                output_directory=$1
                                ;;
        -h | --help )           usage
                                exit
                                ;;
        * )                     usage
                                exit 1
    esac
    shift
done

if [ -z "$output_directory" ]; then
    echo "please define an output directory..."
    usage
    exit 1
fi
output_absolute_dir="$(realpath ${output_directory})"
echo "output directory is ${output_absolute_dir}"

# generate a python-flask server
temp_folder=${PWD}/tmp
if [ -d "$temp_folder" ]; then
  rm -rf $temp_folder
fi
mkdir ${temp_folder}
./openapi_codegen.sh -i ${input_file} -o ${temp_folder} -g ${generator}

if [ ! -d "$output_directory" ]; then
  mkdir ${output_directory}
fi

echo "retrieving util.py..."
mv -uf ${temp_folder}/${generator}/openapi_server/util.py ${output_directory}/util.py
echo "retrieving __init__.py..."
mv -uf ${temp_folder}/${generator}/openapi_server/__init__.py ${output_directory}/__init__.py
echo "retrieving models..."
if [ ! -d "$output_directory/models" ]; then
  mkdir ${output_directory}/models
fi
mv -uf ${temp_folder}/${generator}/openapi_server/models/* ${output_directory}/models

echo "cleaning up..."
rm -rf ${temp_folder}