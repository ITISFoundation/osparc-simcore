# dy-2Dgraph

This service is based on a jupyter notebook enhanced with a set of notebook extensions and pre-installed pandas and plotly python packages.

## Table and 2D graphs

By default this service will load a comma-separated value file using [pandas](https://pandas.pydata.org/) and display its contents as a table and a 2D scatter plot using [plotly](https://plot.ly/#/).

## Overview

A reminder of the architecture is visible here ![workbench architecture](./diagrams/workbench_workflow_diagram.svg)

A simple workflow is shown in the workbench containing Filereader, Computational pipeline and Analysis entities. Each of these entities interacts with some kind of data on an external S3 storage. The configuration of the workflow and of the node connections is stored in an external database.

A python-based node needs some mechanism to access its input/output ports configuration and the data that might have been assigned to it. Therefore the simcoreapi package comes in play.

A workbench node input/output ports json-based configuration is described as follow:

```javascript
{
    "version":"0.1",
    "inputs": [
        {
            "key": "in_1",
            "label": "computational data",
            "description": "these are computed data out of a pipeline",
            "type": "file-url",
            "value": "/home/jovyan/data/outputControllerOut.dat",
            "timestamp": "2018-05-23T15:34:53.511Z"
        },
        {
            "key": "in_5",
            "label": "some number",
            "description": "numbering things",
            "type": "integer",
            "value": "666",
            "timestamp": "2018-05-23T15:34:53.511Z"
        }
    ],
    "outputs": [
        {
            "key": "out_1",
            "label": "some boolean output",
            "description": "could be true or false...",
            "type": "bool",
            "value": "null",
            "timestamp": "2018-05-23T15:34:53.511Z"
        }
    ]
}
```

### simcoreapi package

The simcoreapi python package is a component of this service that allows direct access to the service input and output connections.

The simcoreapi package takes care of reading/writing out the configuration of the node and exposing the inputs/outputs defined in the workbench.

Through its _get()_ method an input/output is automatically converted to a fitting python type.
Using the _set()_ method with an output will automatically convert it to a string and update the port configuration.

### (in development)

The simcoreapi seamlessly pulls any necessary data from the external storage to the local storage. It will also take care of updating it in case it changed.
Reversely the simcoreapi takes care of pushing data back to the external storage from the local storage if there is such an output defined for the node.

### basic usage

```python
from simcoreapi import PORTS
# access input0 as defined as defined in the workbench
input0 = PORTS.inputs[0]
print(input0.key)
print(input0.value)

# access input1 and a file path as defined in the workbench
data_path = PORTS.inputs[1].get()

# set the output0 to some value
output0 = PORTS.outputs[0]
output0.set(someFctThatOutputsABoolean())

resultingFilePath = someFctThatOutputsAFile()
output1 = PORTS.outputs[1]
output1.set(resultingFilePath)
```

## docker

This project uses a simple ``Dockerfile`` based on the dy-jupiter service docker image.

To build the target image execute the following in a shell environment:

```bash
cd path/to/dy-2Dgraph
docker build .
```