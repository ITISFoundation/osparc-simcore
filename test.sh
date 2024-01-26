#!/bin/sh
num_cpus=$(nproc)
DASK_NTHREADS=${DASK_NTHREADS:="$num_cpus"}
echo ${DASK_NTHREADS}
