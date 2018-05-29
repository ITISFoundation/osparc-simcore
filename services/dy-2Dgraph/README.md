# dy-2Dgraph

This service is based on a jupyter notebook enhanced with a set of notebook extensions and pre-installed pandas and plotly python packages.

## Table and 2D graphs

By default this service will load a comma-separated value file using [pandas](https://pandas.pydata.org/) and display its contents as a table and a 2D scatter plot using [plotly](https://plot.ly/#/).

## Overview

A reminder of the architecture is visible here ![workbench architecture](./diagrams/workbench_workflow_diagram.svg)

A simple workflow is shown in the workbench containing Filereader, Computational pipeline and Analysis entities. Each of these entities interacts with some kind of data on an external S3 storage. The configuration of the workflow and of the node connections is stored in an external database.

A python-based node needs some mechanism to access its input/output ports configuration and the data that might have been assigned to it. Therefore the simcore_api package comes in play.

### simcore_api package

The simcore_api python package is a component of this service that allows direct access to the service input and output connections.

The simcore_api package takes care of reading out the configuration of the node and exposing the inputs/outputs defined in the workbench.

### (in development)

The simcore_api seamlessly pulls any necessary data from the external storage to the local storage. It will also take care of updating it in case it changed.
Reversely the simcore_api takes care of pushing data back to the external storage from the local storage if there is such an output defined for the node.

### basic usage

```python
from simcore_api import simcore
# access input0 as defined as defined in the workbench
input0 = simcore.inputs[0]
print(input0.key)
print(input0.value)

# access input1 and a file path as defined in the workbench
data_path = simcore.inputs[1].get()

# set the output0 to some value
output0 = simcore.outputs[0]
output0.set(someFctThatOutputsABoolean())

resultingFilePath = someFctThatOutputsAFile()
output1 = simcore.outputs[1]
output1.set(resultingFilePath)
```

## docker

This project uses a simple ``Dockerfile`` based on the dy-jupiter service docker image.

To build the target image execute the following in a shell environment:

```bash
cd path/to/dy-2Dgraph
docker build .
```