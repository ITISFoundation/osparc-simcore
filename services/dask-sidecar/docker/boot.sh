#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "

# BOOTING application ---------------------------------------------
echo "$INFO" "Booting in ${SC_BOOT_MODE} mode ..."
echo "  User    :$(id "$(whoami)")"
echo "  Workdir :$(pwd)"
echo "  env     :$(env)"

if [ "${SC_BUILD_TARGET}" = "development" ]; then
  echo "$INFO" "Environment :"
  printenv | sed 's/=/: /' | sed 's/^/    /' | sort
  echo "$INFO" "Python :"
  python --version | sed 's/^/    /'
  command -v python | sed 's/^/    /'
  cd services/dask-sidecar || exit 1
  pip install --no-cache-dir -r requirements/dev.txt
  cd - || exit 1
  echo "$INFO" "PIP :"
  pip list | sed 's/^/    /'
fi

# RUNNING application ----------------------------------------
#
# - If DASK_START_AS_SCHEDULER is set, then it boots as scheduler otherwise as worker
# - SEE https://docs.dask.org/en/latest/setup/cli.html
# - SEE https://stackoverflow.com/questions/3601515/how-to-check-if-a-variable-is-set-in-bash
# - FIXME: create command prefix: https://unix.stackexchange.com/questions/444946/how-can-we-run-a-command-stored-in-a-variable
#

if [ ${DASK_START_AS_SCHEDULER+x} ]; then
  SCHEDULER_VERSION=$(dask-scheduler --version)

  echo "$INFO" "Starting as ${SCHEDULER_VERSION}..."
  if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then

    exec watchmedo auto-restart --recursive --pattern="*.py" -- \
      dask-scheduler

  else

    exec dask-scheduler

  fi
else
  DASK_WORKER_VERSION=$(dask-worker --version)
  DASK_SCHEDULER_ADDRESS="tcp://${DASK_SCHEDULER_HOST}:8786"

  #
  # DASK RESOURCES DEFINITION
  #
  # Following resources are defined on a dask-sidecar for computational tasks:
  # CPU: number of CPUs available (= num of processing units - DASK_SIDECAR_NUM_NON_USABLE_CPUS)
  # GPU: number GPUs available (= num of GPUs if a nvidia-smi can be run inside a docker container)
  # RAM: amount of RAM available (= CPU/nproc * total virtual memory given by python psutil - DASK_SIDECAR_NON_USABLE_RAM)
  # MPI: backwards-compatibility (deprecated if core_number = TARGET_MPI_NODE_CPU_COUNT set to 1)

  # CPUs
  num_cpus=$(($(nproc) - ${DASK_SIDECAR_NUM_NON_USABLE_CPUS:-2}))
  if [ "$num_cpus" -le 0 ]; then
    # ensure the minimal amount of cpus is 1 in case the system is a dual-core or less (CI case for instance)
    num_cpus=1
  fi

  # GPUs
  num_gpus=$(python -c "from simcore_service_dask_sidecar.utils import num_available_gpus; print(num_available_gpus());")

  # RAM (is computed similarly as the default dask-sidecar computation)
  ram=$(($(python -c "import psutil; print(int(psutil.virtual_memory().total * $num_cpus/$(nproc)))") - ${DASK_SIDECAR_NON_USABLE_RAM:-0}))

  # overall resources available on the dask-sidecar (CPUs and RAM are always available)
  resources="CPU=$num_cpus,RAM=$ram"

  # add the GPUs if there are any
  if [ "$num_gpus" -gt 0 ]; then
    resources="$resources,GPU=$num_gpus"
  fi

  # add the MPI if possible
  if [ ${TARGET_MPI_NODE_CPU_COUNT+x} ]; then
    if [ "$(nproc)" -eq "${TARGET_MPI_NODE_CPU_COUNT}" ]; then
      resources="$resources,MPI=1"
    fi
  fi

  # find if a cluster id was setup in the docker daemon labels
  cluster_id=$(python -c "from simcore_service_dask_sidecar.utils import cluster_id; print(cluster_id());")
  if [ "$cluster_id" != "None" ]; then
    resources="$resources,$cluster_id=1"
  fi

  #
  # DASK RESOURCES DEFINITION --------------------------------- END
  #

  #
  # 'daemonic processes are not allowed to have children' arises when running the sidecar.cli
  # because multi-processing library is used by the sidecar and the nanny does not like it
  # setting --no-nanny fixes this: see https://github.com/dask/distributed/issues/2142
  echo "$INFO" "Starting as a ${DASK_WORKER_VERSION} -> ${DASK_SCHEDULER_ADDRESS} ..."
  echo "$INFO" "Worker resources set as: $resources"
  if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then
    exec watchmedo auto-restart --recursive --pattern="*.py" -- \
      dask-worker "${DASK_SCHEDULER_ADDRESS}" \
      --local-directory /tmp/dask-sidecar \
      --preload simcore_service_dask_sidecar.tasks \
      --reconnect \
      --no-nanny \
      --nprocs 1 \
      --nthreads "$num_cpus" \
      --dashboard-address 8787 \
      --memory-limit "$ram" \
      --resources "$resources" \
      --name "dask-sidecar_$(hostname)_$(date +'%Y-%m-%d_%T')_$$"
  else
    exec dask-worker "${DASK_SCHEDULER_ADDRESS}" \
      --local-directory /tmp/dask-sidecar \
      --preload simcore_service_dask_sidecar.tasks \
      --reconnect \
      --no-nanny \
      --nprocs 1 \
      --nthreads "$num_cpus" \
      --dashboard-address 8787 \
      --memory-limit "$ram" \
      --resources "$resources" \
      --name "dask-sidecar_$(hostname)_$(date +'%Y-%m-%d_%T')_$$"
  fi
fi
