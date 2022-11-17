#!/bin/sh

usage()
{
    echo "usage: copy_database_volume.sh [[[-h host ] [[-f folder] | [-v volume]] [-t target]] | [-h]]"
}


if [ $# -eq 0 ]; then
    usage
    exit 1
fi


while [ "$1" != "" ]; do
    case $1 in
        -h | --host )           shift
                                host=$1
                                ;;
        -f | --folder )         shift
                                folder=$1
                                ;;
        -v | --volume )         shift
                                volume=$1
                                ;;
        -t | --target )         shift
                                target=$1
                                ;;
        -h | --help )           usage
                                exit
                                ;;
        * )                     usage
                                exit 1
    esac
    shift
done

if [ -z $host ] || [ -z $target ] || ([ -z $folder ] && [ -z $volume ]); then
  usage
  exit 1
fi

if [ ! -z $folder ] && [ ! -z $volume ]; then
  echo "cannot use both --folder and --volume arguments"
  usage
  exit 1
fi

set -o errexit
# set -o nounset

IFS=$(printf '\n\t')


if [ ! -z $folder ]; then
  #from folder to target volume
  ssh $host \
    "tar -cf - $folder " \
    | \
    docker run --rm -i -v "$target":/to alpine ash -c "cd /to ; tar -xpvf - "
else
  #from docker volume to target volume
  ssh $host \
    "docker run --rm -v $volume:/from alpine ash -c 'cd /from ; tar -cf - . '" \
    | \
    docker run --rm -i -v "$target":/to alpine ash -c "cd /to ; tar -xpvf - "
fi
