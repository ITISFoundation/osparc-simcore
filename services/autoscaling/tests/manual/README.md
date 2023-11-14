# autoscaling service manual testing

The autoscaling service may be started either in computational mode or in dynamic mode.

The computational mode is used in conjunction with a dask-scheduler/dask-worker subsystem.
The dynamic mode is used directly with docker swarm facilities.

### requirements

1. AWS EC2 access
2. a machine running in EC2 with docker installed and access to osparc-simcore repository


## computational mode

When ```DASK_MONITORING_URL``` is set the computational mode is enabled.


### instructions

1. prepare autoscaling

```bash
# run on EC2 instance
git clone https://github.com/ITISFoundation/osparc-simcore.git
cd osparc-simcore/services/autoscaling
make build-devel # this will build the autoscaling devel image
```

2. setup environment variables
```bash
# run on EC2 instance
cd osparc-simcore/services/autoscaling/tests/manual
make .env # generate an initial .env file
nano .env # edit .env and set the variables as needed
```

3. start autoscaling/dask-scheduler stack
```bash
# run on EC2 instance
cd osparc-simcore/services/autoscaling/tests/manual
make up-computational-devel # this will deploy the autoscaling/dask-scheduler/worker stack
```

4. start some dask tasks to trigger autoscaling
```bash
# run on any host
cd osparc-simcore/services/autoscaling
make install-dev
pip install ipython
ipython
```
```python
import distributed
# connect to the dask-scheduler running on the EC2 machine
client = distributed.Client("tcp://{EC2_INSTANCE_PUBLIC_IP}:8786")

# some dummy test function to run remotely
def test_fct(x,y):
  return x+y

# send the task over to the dask-scheduler
future = client.submit(test_fct, 3, 54, resources={"CPU": 1}, pure=False)

# this will trigger the autoscaling to create a new machine (ensure the EC2_INSTANCES_ALLOWED_TYPES variable allows for machines capable of running the job with the wanted resources)
# after about 3 minutes the job will be run
future.done() # shall return True once done

# remove the future from the dask-scheduler memory, shall trigger the autoscaling service to remove the created machine
del future
```


## dynamic mode

When ```NODES_MONITORING_NEW_NODES_LABELS```, ```NODES_MONITORING_NODE_LABELS``` and ```NODES_MONITORING_SERVICE_LABELS``` are set the dynamic mode is enabled.

### instructions

1. prepare autoscaling

```bash
# run on EC2 instance
git clone https://github.com/ITISFoundation/osparc-simcore.git
cd osparc-simcore/services/autoscaling
make build-devel # this will build the autoscaling devel image
```

2. setup environment variables
```bash
# run on EC2 instance
cd osparc-simcore/services/autoscaling/tests/manual
make .env # generate an initial .env file
nano .env # edit .env and set the variables as needed
```

3. start autoscaling stack
```bash
# run on EC2 instance
cd osparc-simcore/services/autoscaling/tests/manual
make up-devel # this will deploy the autoscaling stack
```

4. start some docker services to trigger autoscaling
```bash
# run on EC2 instance
docker service create --reserve-cpu=4 --reserve-memory=1GiB --constraint=node.label==testing.monitored-node --label=testing.monitored-service redis # will create a redis service reserving 4 CPUs and 1GiB of RAM
```
