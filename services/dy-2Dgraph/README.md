# dy-2Dgraph

This service contains several sub-services for displaying data in a meaningful way such as with tables and 2D/3D graphs. It demonstrates the usage of the simcore-sdk package together with the well known jupyter notebook to create reproducible ways of displaying data. Depending on the use-cases the jupyter notebooks are enhanced with packages such as pandas, matplotlib and plotly to show how easy one can post-process data.

## Table and 2D graphs

By default this service will load a comma-separated value file using [pandas](https://pandas.pydata.org/) and display its contents as a table and a 2D scatter plot using [plotly](https://plot.ly/#/).

## Overview

### Commons

For each use-case a jupyter notebook-based service is created that will:

1. Pull the information about the node ports configuration from the simcore database when needed in the jupyter notebook
2. Pull one or more input files in the service file system from the previous node(s) when needed in the jupyter notebook
3. Parse some data file using the python pandas package (such as comma-separated values)
4. Display the data using python matplotlib/plotly packages

### simcore-sdk package

The simcore-sdk python package is used here to allow direct access to the node input and output connections.

The simcore-sdk package takes care of reading/writing out the configuration of the node and exposing the inputs/outputs defined in the workbench.

Through its _get()_ method an input/output is automatically converted to a fitting python type. If the pointed data is located on S3 storage it will be automatically downloaded to the local storage and its file path will be returned.
Using the _set()_ method with an output will automatically convert it to a string and update the port configuration in the database.

### basic demo usage

1. rename _services/dy-2Dgraph/use-cases/.env-devel_ to _.env_
2. open terminal and do
    ```bash
    make build-devel
    make up-devel
    ```
3. open url [localhost:1234](localhost:1234) to see 0d use case graphs
4. open url [localhost:1235](localhost:1235) to see 1d use case graphs
5. open url [localhost:1236](localhost:1236) to see 2d use case graphs
6. open url [localhost:9001](localhost:9001) to see the s3 file manager UI
7. open url [localhost:18080](localhost:18080) to see the adminer (db visualiser)

### basic usage of simcore-sdk/nodeports package

```python
from simcore-sdk.nodeports import PORTS
# access input0 as defined as defined in the workbench
input0 = PORTS.inputs[0]
print(input0.key)
print(input0.value)
# if the key is known one can also do
input0 = PORTS.inputs["key"]

# access input1 and a file path as defined in the workbench
data_path = PORTS.inputs[1].get()

# set the output0 to some value
output0 = PORTS.outputs[0]
output0.set(someFctThatOutputsABoolean())

resultingFilePath = someFctThatOutputsAFile()
output1 = PORTS.outputs[1]
output1.set(resultingFilePath)
```