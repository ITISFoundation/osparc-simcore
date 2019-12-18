#!/bin/bash
set -e

cd $(dirname $0)
usage()
{
    echo "usage: temp_generate_openapi.sh [[[-i input]] | [-h help]]"
}

apihub_specs_dir=
# process arguments
while [ "$1" != "" ]; do
    case $1 in
        -i | --input )          shift
                                apihub_specs_dir=$1
                                ;;
        -h | --help )           usage
                                exit
                                ;;
        * )                     usage
                                exit 1
    esac
    shift
done

if [ -z "$apihub_specs_dir" ]; then
    echo "please define an apihub specs directory..."
    usage
    exit 1
fi

docker run \
    -v $apihub_specs_dir:/input \
    -v ${PWD}/src/simcore_service_director/oas3/v0:/output \
    itisfoundation/oas_resolver \
    /input/director/v0/openapi.yaml \
    /output/openapi.yaml
