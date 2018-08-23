#/bin/bash

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
mkdir ${temp_folder}
./openapi_codegen.sh -i ${input_file} -o ${temp_folder} -g ${generator}

echo "retrieving models..."
# let-s move the model files
mv ${temp_folder}/${generator}/openapi_server/models ${output_directory}
echo "retrieving util.py..."
mv ${temp_folder}/${generator}/openapi_server/util.py ${output_directory}
echo "retrieving __init__.py..."
mv ${temp_folder}/${generator}/openapi_server/__init__.py ${output_directory}

echo "cleaning up..."
rm -rf ${temp_folder}