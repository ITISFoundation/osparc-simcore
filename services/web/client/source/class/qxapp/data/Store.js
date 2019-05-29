/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Singleton class that is used as entrypoint to the webserver.
 *
 * All data transfer communication goes through the qxapp.data.Store.
 *
 * *Example*
 *
 * Here is a little example of how to use the class.
 *
 * <pre class='javascript'>
 *   let services = qxapp.data.Store.getInstance().getServices();
 * </pre>
 */

qx.Class.define("qxapp.data.Store", {
  extend: qx.core.Object,

  type : "singleton",

  construct: function() {
    this.__reloadingServices = false;
    this.__servicesCached = {};
  },

  events: {
    "servicesRegistered": "qx.event.type.Event",
    // "fakeFiles": "qx.event.type.Event",
    "myDocuments": "qx.event.type.Event",
    "nodeFiles": "qx.event.type.Event",
    "presignedLink": "qx.event.type.Event",
    "fileCopied": "qx.event.type.Event",
    "deleteFile": "qx.event.type.Event"
  },

  members: {
    __reloadingServices: null,
    __servicesCached: null,

    __matchPortType: function(typeA, typeB) {
      if (typeA === typeB) {
        return true;
      }
      let mtA = qxapp.data.MimeType.getMimeType(typeA);
      let mtB = qxapp.data.MimeType.getMimeType(typeB);
      return mtA && mtB &&
        new qxapp.data.MimeType(mtA).match(new qxapp.data.MimeType(mtB));
    },

    areNodesCompatible: function(topLevelPort1, topLevelPort2) {
      console.log("areNodesCompatible", topLevelPort1, topLevelPort2);
      return topLevelPort1.isInput !== topLevelPort2.isInput;
    },

    arePortsCompatible: function(port1, port2) {
      return port1.type && port2.type && this.__matchPortType(port1.type, port2.type);
    },

    getNodeMetaData: function(key, version) {
      let metaData = null;
      if (key && version) {
        metaData = qxapp.utils.Services.getFromObject(this.__servicesCached, key, version);
        if (metaData) {
          metaData = qxapp.utils.Utils.deepCloneObject(metaData);
          if (metaData.key === "simcore/services/dynamic/modeler/webserver") {
            metaData.outputs["modeler"] = {
              "label": "Modeler",
              "displayOrder":0,
              "description": "Modeler",
              "type": "node-output-tree-api-v0.0.1"
            };
            delete metaData.outputs["output_1"];
          }
          return metaData;
        }
        const moreServices = this.getFakeServices().concat(this.getBuiltInServices());
        metaData = qxapp.utils.Services.getFromArray(moreServices, key, version);
        if (metaData) {
          return qxapp.utils.Utils.deepCloneObject(metaData);
        }
      }
      return null;
    },

    getBuiltInServices: function() {
      const builtInServices = [{
        key: "simcore/services/frontend/file-picker",
        version: "1.0.0",
        type: "dynamic",
        name: "File Picker",
        description: "File Picker",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputs: {},
        outputs: {
          outFile: {
            displayOrder: 0,
            label: "File",
            description: "Chosen File",
            type: "data:*/*"
          }
        }
      }, {
        key: "simcore/services/frontend/nodes-group",
        version: "1.0.0",
        type: "group",
        name: "Group of nodes",
        description: "Groups a collection of nodes in a single node",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch"
      }, {
        key: "simcore/services/frontend/multi-plot",
        version: "1.0.0",
        type: "group",
        dedicatedWidget: true,
        name: "2D plot - Multi",
        description: "2D plot - Multi",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputs: {
          "input_1": {
            "label": "input 1",
            "displayOrder": 0,
            "description": "Input 1",
            "type": "data:*/*"
          },
          "input_2": {
            "label": "input 2",
            "displayOrder": 1,
            "description": "Input 2",
            "type": "data:*/*"
          },
          "input_3": {
            "label": "input 3",
            "displayOrder": 2,
            "description": "Input 3",
            "type": "data:*/*"
          },
          "input_4": {
            "label": "input 4",
            "displayOrder": 3,
            "description": "Input 4",
            "type": "data:*/*"
          },
          "input_5": {
            "label": "input 5",
            "displayOrder": 4,
            "description": "Input 5",
            "type": "data:*/*"
          }
        },
        outputs: {},
        innerNodes: {
          "inner1_raw": {
            key: "simcore/services/dynamic/raw-graphs",
            version: "2.8.0",
            inputNodes: [],
            outputNode: true
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/neuroman",
        version: "0.0.0",
        type: "dynamic",
        name: "Neuroman",
        description: "Neuroman",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputsDefault: {
          defaultNeuromanModels: {
            displayOrder: 0,
            label: "Neuroman models",
            description: "Neuroman models",
            type: "node-output-list-api-v0.0.1"
          }
        },
        inputs: {
          inModel: {
            displayOrder: 0,
            label: "Input model",
            description: "Model to be loaded",
            type: "data:*/*"
          }
        },
        outputs: {
          modeler: {
            displayOrder: 0,
            label: "Modeler",
            description: "Modeler Live link",
            type: "node-output-tree-api-v0.0.1"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/StimulationSelectivity",
        version: "0.0.0",
        type: "computational",
        name: "Stimulation Selectivity Evaluator",
        description: "Evalutes Stimulation Selectivity",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputsDefault: {
          defaultStimulationSelectivity: {
            displayOrder: 0,
            label: "Subgroups",
            description: "Subgroups",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          modeler: {
            displayOrder: 0,
            label: "Modeler",
            description: "Live Link to Modeler",
            type: "data:application/s4l-api/modeler"
          },
          mapper: {
            displayOrder: 1,
            label: "Subgroups",
            description: "Maps Model entities into Subgroups",
            type: "mapper",
            maps: {
              leaf: "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/Neurons"
            }
          }
        },
        outputs: {
          stimulationFactor: {
            displayOrder: 0,
            label: "Stimulation factor",
            description: "Stimulation factor",
            type: "number"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Modeler",
        version: "0.0.0",
        type: "dynamic",
        name: "Modeler",
        description: "Modeler",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputs: {},
        outputs: {
          modeler: {
            displayOrder: 0,
            label: "Modeler",
            description: "Modeler Live link",
            type: "node-output-tree-api-v0.0.1"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/MaterialDB",
        version: "0.0.0",
        type: "computational",
        name: "MaterialDB",
        description: "Material Database",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputs: {},
        outputs: {
          materialDB: {
            displayOrder: 0,
            label: "MaterialDB",
            description: "MaterialDB Live link",
            type: "node-output-tree-api-v0.0.1"
          }
        }
      }, {
        key: "simcore/services/demodec/container/itis/s4l/Simulator/LF",
        version: "0.0.0",
        type: "container",
        name: "LF Simulator",
        description: "LF Simulator",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputs: {
          modeler: {
            displayOrder: 0,
            label: "Modeler",
            description: "Live link to Modeler",
            type: "data:application/s4l-api/modeler"
          },
          materialDB: {
            displayOrder: 1,
            label: "MaterialDB",
            description: "Live link to Material DB",
            type: "data:application/s4l-api/materialDB"
          }
        },
        outputs: {
          outFile: {
            displayOrder: 0,
            label: "File",
            description: "LF Solver Input File",
            type: "data:application/hdf5"
          }
        },
        innerNodes: {
          "inner1": {
            key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Setup",
            version: "0.0.0",
            inputNodes: [],
            outputNode: false
          },
          "inner2": {
            key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Materials",
            version: "0.0.0",
            inputNodes: [
              "modeler",
              "materialDB"
            ],
            outputNode: false
          },
          "inner3": {
            key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Boundary",
            version: "0.0.0",
            inputNodes: [
              "modeler"
            ],
            outputNode: false
          },
          "inner4": {
            key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Sensors",
            version: "0.0.0",
            inputNodes: [
              "modeler"
            ],
            outputNode: false
          },
          "inner5": {
            key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Grid",
            version: "0.0.0",
            inputNodes: [
              "modeler"
            ],
            outputNode: false
          },
          "inner6": {
            key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Voxel",
            version: "0.0.0",
            inputNodes: [
              "modeler"
            ],
            outputNode: false
          },
          "inner7": {
            key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/SolverSettings",
            version: "0.0.0",
            inputNodes: [],
            outputNode: true
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Setup",
        version: "0.0.0",
        type: "computational",
        name: "LF Setup",
        description: "LF Simulator Setup Settings",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputs: {
          frequency: {
            displayOrder: 0,
            label: "Frequency",
            description: "Frequency (Hz)",
            type: "number",
            defaultValue: 1000
          }
        },
        outputs: {
          setupSetting: {
            displayOrder: 0,
            label: "LF-Setup",
            description: "LF Setup Settings",
            type: "data:application/s4l-api/settings"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Materials",
        version: "0.0.0",
        type: "computational",
        name: "LF Materials",
        description: "LF Simulator Material Settings",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputsDefault: {
          defaultLFMaterials: {
            displayOrder: 0,
            label: "Default Material Settings",
            description: "Default Material Settings",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          updateDispersive: {
            displayOrder: 0,
            label: "Enable automatic update of dispersive materials",
            description: "Enable automatic update of dispersive materials",
            type: "boolean",
            defaultValue: false
          },
          modeler: {
            displayOrder: 1,
            label: "Modeler",
            description: "Live Link to Modeler",
            type: "data:application/s4l-api/modeler"
          },
          materialDB: {
            displayOrder: 2,
            label: "MaterialDB",
            description: "Live Link to Material DB",
            type: "data:application/s4l-api/materialDB"
          },
          mapper: {
            displayOrder: 3,
            label: "Material Settings",
            description: "Maps Model entities into Materials",
            type: "mapper",
            maps: {
              branch: "simcore/services/demodec/dynamic/itis/s4l/MaterialDB",
              leaf: "simcore/services/dynamic/modeler/webserver"
            },
            defaultValue: [{
              "Air-UUID": [
                "Background"
              ]
            }]
          }
        },
        outputs: {
          materialSetting: {
            displayOrder: 0,
            label: "MaterialSettings",
            description: "Material Settings",
            type: "data:application/s4l-api/settings"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Boundary",
        version: "0.0.0",
        type: "computational",
        name: "LF Boundary Conditions",
        description: "LF Simulator Boundary Conditions",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputsDefault: {
          defaultLFBoundaries: {
            displayOrder: 0,
            label: "Default Boundary Settings",
            description: "Default Boundary Settings",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          modeler: {
            displayOrder: 0,
            label: "Modeler",
            description: "Live Link to Modeler",
            type: "data:application/s4l-api/modeler"
          },
          mapper: {
            displayOrder: 1,
            label: "Boundary Conditions",
            description: "Maps Model entities into Boundary Conditions",
            type: "mapper",
            maps: {
              leaf: "simcore/services/dynamic/modeler/webserver"
            },
            defaultValue: [{
              "Neumann-UUID": [
                "Plane X+",
                "Plane X-",
                "Plane Y+",
                "Plane Y-",
                "Plane Z+",
                "Plane Z-"
              ]
            }]
          }
        },
        outputs: {
          boundarySetting: {
            displayOrder: 0,
            label: "BoundaryConditions",
            description: "Boundary Conditions",
            type: "data:application/s4l-api/settings"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Sensors",
        version: "0.0.0",
        type: "computational",
        name: "LF Sensors",
        description: "LF Simulator Sensors Settings",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputsDefault: {
          defaultLFSensors: {
            displayOrder: 0,
            label: "Default Sensors",
            description: "Default Sensors",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          modeler: {
            displayOrder: 0,
            label: "Modeler",
            description: "Live Link to Modeler",
            type: "data:application/s4l-api/modeler"
          },
          mapper: {
            displayOrder: 1,
            label: "Sensor Settings",
            description: "Maps Model entities into Sensor Settings",
            type: "mapper",
            maps: {
              leaf: "simcore/services/dynamic/modeler/webserver"
            },
            defaultValue: [{
              "Field-Sensor-UUID": [
                "Overall Field"
              ]
            }]
          }
        },
        outputs: {
          sensorSetting: {
            displayOrder: 0,
            label: "SensorSettings",
            description: "Sensor Settings",
            type: "data:application/s4l-api/settings"
          },
          sensorSettingAPI: {
            displayOrder: 1,
            label: "LF Sensors",
            description: "LF Sensors",
            type: "node-output-tree-api-v0.0.1"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Grid",
        version: "0.0.0",
        type: "computational",
        name: "LF Grid",
        description: "LF Simulator Grid Settings",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputs: {
          modeler: {
            displayOrder: 0,
            label: "Modeler",
            description: "Live Link to Modeler",
            type: "data:application/s4l-api/modeler"
          },
          homogeneous: {
            displayOrder: 1,
            label: "Homogeneous grid",
            description: "Homogeneous grid",
            type: "boolean",
            defaultValue: true
          },
          resolution: {
            displayOrder: 2,
            label: "Resolution (mm)",
            description: "Resolution in mm",
            type: "number",
            defaultValue: 1
          }
        },
        outputs: {
          gridSetting: {
            displayOrder: 0,
            label: "GridSettings",
            description: "Grid Settings",
            type: "data:application/s4l-api/settings"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Voxel",
        version: "0.0.0",
        type: "computational",
        name: "LF Voxels",
        description: "LF Simulator Voxel Settings",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputs: {
          modeler: {
            displayOrder: 0,
            label: "Modeler",
            description: "Live Link to Modeler",
            type: "data:application/s4l-api/modeler"
          },
          voxelEngine: {
            displayOrder: 1,
            label: "Used Voxel Engine",
            description: "Used Voxel Engine",
            type: "string",
            defaultValue: "Topological Voxeler"
          },
          maximumFraction: {
            displayOrder: 2,
            label: "Maximum Fraction",
            description: "Maximum Fraction",
            type: "number",
            defaultValue: 21
          },
          congruentSubgrid: {
            displayOrder: 3,
            label: "Congruent Subgrid Voxeling",
            description: "Congruent Subgrid Voxeling",
            type: "boolean",
            defaultValue: true
          }
        },
        outputs: {
          voxelSetting: {
            displayOrder: 0,
            label: "VoxelSettings",
            description: "Voxel Settings",
            type: "data:application/s4l-api/settings"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/SolverSettings",
        version: "0.0.0",
        type: "computational",
        name: "LF Solver Settings",
        description: "LF Simulator Solver Settings",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputs: {
          parallelization: {
            displayOrder: 0,
            label: "Parallelization Handling",
            description: "Parallelization Handling",
            type: "string",
            defaultValue: "Manual"
          },
          processes: {
            displayOrder: 1,
            label: "Number of processes",
            description: "Number of processes",
            type: "number",
            defaultValue: 1
          },
          priority: {
            displayOrder: 2,
            label: "Priority in queue",
            description: "Priority in queue",
            type: "number",
            defaultValue: 0
          },
          convergence: {
            displayOrder: 3,
            label: "Convergence Tolerance",
            description: "Convergence Tolerance",
            type: "string",
            defaultValue: "Medium"
          },
          additionalOptions: {
            displayOrder: 4,
            label: "Additional Solver Options",
            description: "Additional Solver Options",
            type: "string",
            defaultValue: ""
          }
        },
        outputs: {
          outFile: {
            displayOrder: 0,
            label: "Input file",
            description: "LF Solver Input File",
            type: "data:application/hdf5"
          }
        }
      }, {
        key: "simcore/services/demodec/computational/itis/Solver-LF",
        version: "0.0.0",
        type: "computational",
        name: "LF Solver",
        description: "LF Solver",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputs: {
          inFile: {
            displayOrder: 0,
            label: "Input file",
            description: "LF Solver Input File",
            type: "data:application/hdf5"
          }
        },
        outputs: {
          outFile: {
            displayOrder: 0,
            label: "Output file",
            description: "LF Solver Output File",
            type: "data:application/hdf5"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/Setup",
        version: "0.0.0",
        type: "computational",
        name: "Neuron Setup",
        description: "Neuron Simulator Setup Settings",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputs: {
          temperature: {
            displayOrder: 0,
            label: "Global Temperature (°C)",
            description: "Global Temperature (°C)",
            type: "number",
            defaultValue: 37
          },
          titration: {
            displayOrder: 1,
            label: "Perform Titration",
            description: "Perform Titration",
            type: "boolean",
            defaultValue: false
          },
          convergence: {
            displayOrder: 2,
            label: "Titration convergence criterion",
            description: "Titration convergence criterion",
            type: "number",
            defaultValue: 1
          },
          actionPotential: {
            displayOrder: 3,
            label: "Action Potential detection method",
            description: "Action Potential detection method",
            type: "string",
            defaultValue: "Threshold"
          },
          threshold: {
            displayOrder: 4,
            label: "Threshold for depolarization (mV)",
            description: "Threshold for depolarization (mV)",
            type: "number",
            defaultValue: 80
          }
        },
        outputs: {
          setupSetting: {
            displayOrder: 0,
            label: "Neuron-Setup",
            description: "Neuron Setup Settings",
            type: "data:application/s4l-api/settings"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/Neurons",
        version: "0.0.0",
        type: "computational",
        name: "Neuron Neurons",
        description: "Neuron Simulator Neurons",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputsDefault: {
          defaultNeurons: {
            displayOrder: 0,
            label: "Default Neurons",
            description: "Default Neurons",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          modeler: {
            displayOrder: 0,
            label: "Modeler",
            description: "Live Link to Modeler",
            type: "data:application/s4l-api/modeler"
          },
          mapper: {
            displayOrder: 1,
            label: "Neurons",
            description: "Maps Model entities into Neurons",
            type: "mapper",
            maps: {
              leaf: "simcore/services/dynamic/modeler/webserver"
            }
          }
        },
        outputs: {
          neuronsSetting: {
            displayOrder: 0,
            label: "NeuronsSettings",
            description: "Neurons Settings",
            type: "node-output-tree-api-v0.0.1"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/Sources",
        version: "0.0.0",
        type: "computational",
        name: "Neuron Sources",
        description: "Neuron Simulator Sources",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputsDefault: {
          defaultNeuronSources: {
            displayOrder: 0,
            label: "Default Sources Settings",
            description: "Default Sources Settings",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          lfSimulation: {
            displayOrder: 0,
            label: "LF Simulation",
            description: "Live Link to LF Simulation",
            type: "data:application/s4l-api/lf-sensor"
          },
          mapper: {
            displayOrder: 1,
            label: "Sources Conditions",
            description: "Maps LF Fields into Sources",
            type: "mapper",
            maps: {
              leaf: "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Sensors"
            }
          }
        },
        outputs: {
          sourceSetting: {
            displayOrder: 0,
            label: "Sources",
            description: "Sources",
            type: "data:application/s4l-api/settings"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/PointProcesses",
        version: "0.0.0",
        type: "computational",
        name: "Neuron Point Processes",
        description: "Neuron Simulator Point Processes",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputsDefault: {
          defaultNeuronPointProcesses: {
            displayOrder: 0,
            label: "Default Point Processes",
            description: "Default Point Processes",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          modeler: {
            displayOrder: 0,
            label: "Modeler",
            description: "Live Link to Modeler",
            type: "data:application/s4l-api/modeler"
          },
          mapper: {
            displayOrder: 1,
            label: "Point Processes",
            description: "Maps Model entities into Point Processes",
            type: "mapper",
            maps: {
              leaf: "simcore/services/dynamic/modeler/webserver"
            }
          }
        },
        outputs: {
          pointProcesses: {
            displayOrder: 0,
            label: "Point Processes",
            description: "Point Processes",
            type: "data:application/s4l-api/settings"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/NetworkConnection",
        version: "0.0.0",
        type: "computational",
        name: "Neuron Network Connection",
        description: "Neuron Simulator Network Connection Settings",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputsDefault: {
          defaultNeuronNetworkConnection: {
            displayOrder: 0,
            label: "Default Network Connection",
            description: "Default Network Connection",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          modeler: {
            displayOrder: 0,
            label: "Modeler",
            description: "Live Link to Modeler",
            type: "data:application/s4l-api/modeler"
          },
          mapper: {
            displayOrder: 1,
            label: "Network Connection",
            description: "Maps Model entities into Network Connection",
            type: "mapper",
            maps: {
              leaf: "simcore/services/dynamic/modeler/webserver"
            }
          }
        },
        outputs: {
          networkConnectionSetting: {
            displayOrder: 0,
            label: "Network Connection Settings",
            description: "Network Connection Settings",
            type: "data:application/s4l-api/settings"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/Sensors",
        version: "0.0.0",
        type: "computational",
        name: "Neuron Sensors",
        description: "Neuron Simulator Sensors Settings",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputsDefault: {
          defaultNeuronSensors: {
            displayOrder: 0,
            label: "Default Sensors",
            description: "Default Sensors",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          modeler: {
            displayOrder: 0,
            label: "Modeler",
            description: "Live Link to Modeler",
            type: "data:application/s4l-api/modeler"
          },
          mapper: {
            displayOrder: 1,
            label: "Sensors",
            description: "Maps Model entities into Sensors",
            type: "mapper",
            maps: {
              leaf: "simcore/services/dynamic/modeler/webserver"
            }
          }
        },
        outputs: {
          sensorSetting: {
            displayOrder: 0,
            label: "Sensors Settings",
            description: "Sensors Settings",
            type: "data:application/s4l-api/settings"
          }
        }
      }, {
        key: "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/SolverSettings",
        version: "0.0.0",
        type: "computational",
        name: "Neuron Solver Settings",
        description: "Neuron Simulator Solver Settings",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputs: {
          parallelization: {
            displayOrder: 0,
            label: "Parallelization Handling",
            description: "Parallelization Handling",
            type: "string",
            defaultValue: "Manual"
          },
          threads: {
            displayOrder: 1,
            label: "Number of threads",
            description: "Number of threads",
            type: "number",
            defaultValue: 1
          },
          priority: {
            displayOrder: 2,
            label: "Priority in queue",
            description: "Priority in queue",
            type: "number",
            defaultValue: 0
          },
          duration: {
            displayOrder: 3,
            label: "Duration (ms)",
            description: "Duration (ms)",
            type: "number",
            defaultValue: 1
          },
          timeStep: {
            displayOrder: 4,
            label: "Time Step (ms)",
            description: "Time Step (ms)",
            type: "number",
            defaultValue: 0.0025
          },
          sectionName: {
            displayOrder: 5,
            label: "Section names for spike detection",
            description: "Section names for spike detection",
            type: "string",
            defaultValue: ""
          }
        },
        outputs: {
          outFile: {
            displayOrder: 0,
            label: "Input file",
            description: "Neuron Solver Input File",
            type: "data:application/hdf5"
          }
        }
      }];
      return builtInServices;
    },

    getFakeServices: function() {
      return qxapp.dev.fake.Data.getFakeServices();
    },

    getServices: function(reload) {
      if (!this.__reloadingServices && reload || Object.keys(this.__servicesCached).length === 0) {
        this.__reloadingServices = true;
        let req = new qxapp.io.request.ApiRequest("/services", "GET");
        req.addListener("success", e => {
          let requ = e.getTarget();
          const {
            data
          } = requ.getResponse();
          const newServices = data.concat(this.getBuiltInServices());
          const services = qxapp.utils.Services.convertArrayToObject(newServices);
          this.__servicesToCache(services, true);
        }, this);

        req.addListener("fail", e => {
          const {
            error
          } = e.getTarget().getResponse();
          console.error("getServices failed", error);
          const moreServices = this.getFakeServices().concat(this.getBuiltInServices());
          const services = qxapp.utils.Services.convertArrayToObject(moreServices);
          this.__servicesToCache(services, false);
        }, this);
        req.send();
        return null;
      }
      return this.__servicesCached;
    },

    __servicesToCache: function(services, fromServer) {
      this.__servicesCached = {};
      this.__addCategoryToServices(services);
      this.__servicesCached = Object.assign(this.__servicesCached, services);
      const data = {
        services: services,
        fromServer: fromServer
      };
      this.fireDataEvent("servicesRegistered", data);
      this.__reloadingServices = false;
    },

    __addCategoryToServices: function(services) {
      const cats = {
        "simcore/services/comp/itis/isolve-emlf": {
          "category": "Solver"
        },
        "simcore/services/comp/itis/neuron-isolve": {
          "category": "Solver"
        },
        "simcore/services/comp/itis/sleeper": {
          "category": "Solver"
        },
        "simcore/services/comp/ucdavis-singlecell-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/ucdavis-1d-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/ucdavis-2d-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/kember-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/demodec/computational/itis/Solver-LF": {
          "category": "Solver"
        },
        "simcore/services/demodec/container/itis/s4l/Simulator/LF": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/MaterialDB": {
          "category": "Solver"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Modeler": {
          "category": "Modeling"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Boundary": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Grid": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Materials": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Sensors": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Setup": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/SolverSettings": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Voxel": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/NetworkConnection": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/Neurons": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/PointProcesses": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/Sensors": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/Setup": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/SolverSettings": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/Sources": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/StimulationSelectivity": {
          "category": "PostPro"
        },
        "simcore/services/demodec/dynamic/itis/s4l/neuroman": {
          "category": "Modeling"
        },
        "simcore/services/dynamic/3d-viewer": {
          "category": "PostPro"
        },
        "simcore/services/dynamic/cc-0d-viewer": {
          "category": "PostPro"
        },
        "simcore/services/dynamic/cc-1d-viewer": {
          "category": "PostPro"
        },
        "simcore/services/dynamic/cc-2d-viewer": {
          "category": "PostPro"
        },
        "simcore/services/dynamic/jupyter-base-notebook": {
          "category": "Notebook"
        },
        "simcore/services/dynamic/jupyter-r-notebook": {
          "category": "Notebook"
        },
        "simcore/services/dynamic/jupyter-scipy-notebook": {
          "category": "Notebook"
        },
        "simcore/services/dynamic/kember-viewer": {
          "category": "PostPro"
        },
        "simcore/services/dynamic/mattward-viewer": {
          "category": "PostPro"
        },
        "simcore/services/dynamic/modeler/webserver": {
          "category": "Modeling"
        },
        "simcore/services/dynamic/modeler/webserverwithrat": {
          "category": "Modeling"
        },
        "simcore/services/dynamic/raw-graphs": {
          "category": "PostPro"
        },
        "simcore/services/frontend/file-picker": {
          "category": "Data"
        },
        "simcore/services/frontend/multi-plot": {
          "category": "PostPro"
        }
      };
      for (const serviceKey in services) {
        if (Object.prototype.hasOwnProperty.call(services, serviceKey)) {
          let service = services[serviceKey];
          if (serviceKey in cats) {
            for (const version in service) {
              let serv = service[version];
              if (Object.prototype.hasOwnProperty.call(service, version)) {
                serv["category"] = cats[serviceKey]["category"];
              } else {
                serv["category"] = "Unknown";
              }
            }
          } else {
            for (const version in service) {
              service[version]["category"] = "Unknown";
            }
          }
        }
      }
    },

    getItemList: function(nodeKey, portKey) {
      return qxapp.dev.fake.Data.getItemList(nodeKey, portKey);
    },

    getItem: function(nodeInstanceUUID, portKey, itemUuid) {
      return qxapp.dev.fake.Data.getItem(nodeInstanceUUID, portKey, itemUuid);
    },

    getFakeFiles: function() {
      let data = qxapp.dev.fake.Data.getObjectList();
      console.log("Fake Files", data);
      this.fireDataEvent("fakeFiles", data);
    },

    getNodeFiles: function(nodeId) {
      const filter = "?uuid_filter=" + encodeURIComponent(nodeId);
      let endPoint = "/storage/locations/0/files/metadata";
      endPoint += filter;
      let reqFiles = new qxapp.io.request.ApiRequest(endPoint, "GET");

      reqFiles.addListener("success", eFiles => {
        const files = eFiles.getTarget().getResponse()
          .data;
        console.log("Node Files", files);
        if (files && files.length>0) {
          this.fireDataEvent("nodeFiles", files);
        }
      }, this);

      reqFiles.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.error("Failed getting Node Files list", error);
      });

      reqFiles.send();
    },

    getMyDocuments: function() {
      // Get available storage locations
      let reqLoc = new qxapp.io.request.ApiRequest("/storage/locations", "GET");

      reqLoc.addListener("success", eLoc => {
        const locations = eLoc.getTarget().getResponse()
          .data;
        for (let i=0; i<locations.length; i++) {
          const locationId = locations[i]["id"];
          if (locationId === 1 && !qxapp.data.Permissions.getInstance().canDo("storage.datcore.read")) {
            continue;
          }
          // Get list of file meta data
          const endPoint = "/storage/locations/" + locationId + "/files/metadata";
          const reqFiles = new qxapp.io.request.ApiRequest(endPoint, "GET");

          reqFiles.addListener("success", eFiles => {
            const files = eFiles.getTarget().getResponse()
              .data;
            console.log("My Files", files);
            if (files && files.length>0) {
              const data = {
                location: locationId,
                files: files
              };
              this.fireDataEvent("myDocuments", data);
            }
          }, this);

          reqFiles.addListener("fail", e => {
            const {
              error
            } = e.getTarget().getResponse();
            console.error("Failed getting Files list", error);
          });

          reqFiles.send();
        }
      }, this);

      reqLoc.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.error("Failed getting Storage Locations", error);
      });

      reqLoc.send();
    },

    getPresignedLink: function(download = true, locationId, fileUuid) {
      if (download && !qxapp.data.Permissions.getInstance().canDo("study.node.data.pull", true)) {
        return;
      }
      if (!download && !qxapp.data.Permissions.getInstance().canDo("study.node.data.push", true)) {
        return;
      }

      // GET: Returns download link for requested file
      // POST: Returns upload link or performs copy operation to datcore
      let res = encodeURIComponent(fileUuid);
      const endPoint = "/storage/locations/" + locationId + "/files/" + res;
      // const endPoint = "/storage/locations/" + locationId + "/files/" + fileUuid;
      const method = download ? "GET" : "PUT";
      let req = new qxapp.io.request.ApiRequest(endPoint, method);

      req.addListener("success", e => {
        const {
          data
        } = e.getTarget().getResponse();
        const presignedLinkData = {
          presignedLink: data,
          locationId: locationId,
          fileUuid: fileUuid
        };
        console.log("presignedLink", presignedLinkData);
        this.fireDataEvent("presignedLink", presignedLinkData);
      }, this);

      req.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.error("Failed getting Presigned Link", error);
      });

      req.send();
    },

    copyFile: function(fromLoc, fileUuid, toLoc, pathId) {
      if (!qxapp.data.Permissions.getInstance().canDo("study.node.data.push", true)) {
        return false;
      }

      // "/v0/locations/1/files/{}?user_id={}&extra_location={}&extra_source={}".format(quote(datcore_uuid, safe=''),
      let fileName = fileUuid.split("/");
      fileName = fileName[fileName.length-1];
      let endPoint = "/storage/locations/"+toLoc+"/files/";
      let parameters = encodeURIComponent(pathId + "/" + fileName);
      parameters += "?extra_location=";
      parameters += fromLoc;
      parameters += "&extra_source=";
      parameters += encodeURIComponent(fileUuid);
      endPoint += parameters;
      let req = new qxapp.io.request.ApiRequest(endPoint, "PUT");

      req.addListener("success", e => {
        const {
          data
        } = e.getTarget().getResponse();
        this.fireDataEvent("fileCopied", data);
      }, this);

      req.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.error(error);
        console.error("Failed copying file", fileUuid, "to", pathId);
        this.fireDataEvent("fileCopied", null);
      });

      req.send();

      return true;
    },

    deleteFile: function(locationId, fileUuid) {
      if (!qxapp.data.Permissions.getInstance().canDo("study.node.data.delete", true)) {
        return false;
      }

      // Deletes File
      let parameters = encodeURIComponent(fileUuid);
      const endPoint = "/storage/locations/" + locationId + "/files/" + parameters;
      let req = new qxapp.io.request.ApiRequest(endPoint, "DELETE");

      req.addListener("success", e => {
        const {
          data
        } = e.getTarget().getResponse();
        this.fireDataEvent("deleteFile", data);
      }, this);

      req.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.error("Failed deleting file", error);
        this.fireDataEvent("deleteFile", null);
      });

      req.send();

      return true;
    }
  }
});
