# autoscaling service manual testing

The autoscaling service may be started either in computational mode or in dynamic mode.

The computational mode is used in conjunction with a dask-scheduler/dask-worker subsystem.
The dynamic mode is used directly with docker swarm facilities.

## computational mode

When ```DASK_MONITORING_URL``` is set the computational mode is enabled.

### requirements

1. AWS EC2 access
2. a machine running in EC2 with docker installed and access to osparc-simcore repository

### instructions

1. prepare autoscaling

```bash
# run on EC2 instance
git clone https://github.com/ITISFoundation/osparc-simcore.git
cd osparc-simcore/services/autoscaling
make build-devel # this will build the autoscaling devel image
make .env # generate an initial .env file
```

2. setup environmenet variables
```bash
# run on EC2 instance
nano .env
```

3. start autoscaling/dask-scheduler stack
```bash
# run on EC2 instance
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
