qx.Class.define("qxapp.dev.fake.neuron.Data", {
  type: "static",

  statics: {
    itemList: {
      "simcore/services/dynamic/itis/s4l/simulator/neuron": [{
        key: "simcore/services/dynamic/itis/s4l/simulator/neuron/setup",
        version: "1.0.0"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/neuron/neurons",
        version: "1.0.0"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/neuron/sources",
        version: "1.0.0"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/neuron/point",
        version: "1.0.0"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/neuron/network",
        version: "1.0.0"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/neuron/sensors",
        version: "1.0.0"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/neuron/solver",
        version: "1.0.0"
      }],

      "defaultNeurons": [{
        key: "SENN-UUID",
        label: "SENN"
      }, {
        key: "MOTOR-UUID",
        label: "MOTOR"
      }, {
        key: "RAT-UUID",
        label: "RAT"
      }, {
        key: "Sweeney-UUID",
        label: "Sweeney"
      }, {
        key: "Hoc-UUID",
        label: "Hoc"
      }],

      "defaultNeuronSources": [{
        key: "SourceSettings-UUID",
        label: "Source Settings"
      }],

      "defaultNeuronPointProcesses": [{
        key: "ExpSyn-UUID",
        label: "ExpSyn"
      }, {
        key: "Exp2Syn-UUID",
        label: "Exp2Syn"
      }, {
        key: "AlphaSynapse-UUID",
        label: "AlphaSynapse"
      }, {
        key: "IClamp-UUID",
        label: "IClamp"
      }],

      "defaultNeuronNetworkConnection": [{
        key: "Synapse-UUID",
        label: "Synapse"
      }],

      "defaultNeuronSensors": [{
        key: "Line-Sensor-UUID",
        label: "Line-Sensor"
      }, {
        key: "Point-Sensor-UUID",
        label: "Point-Sensor"
      }],

      "neuronsSetting": qxapp.dev.fake.modeler.Data.itemList["neuronSim"]
    },

    item: {
      "simcore/services/dynamic/itis/s4l/simulator/neuron/setup": {
        key: "simcore/services/dynamic/itis/s4l/simulator/neuron/setup",
        version: "1.0.0",
        name: "Setup",
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
        }
      },
      "simcore/services/dynamic/itis/s4l/simulator/neuron/neurons": {
        key: "simcore/services/dynamic/itis/s4l/simulator/neuron/neurons",
        version: "1.0.0",
        name: "Neurons",
        inputsDefault: {
          defaultNeurons: {
            displayOrder: 0,
            label: "Default Neurons",
            description: "Default Neurons",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          mapper: {
            displayOrder: 0,
            label: "Neurons",
            description: "Maps Model entities into Neurons",
            type: "mapper",
            maps: {
              leaf: "simcore/services/dynamic/modeler/webserver"
            }
          }
        }
      },
      "simcore/services/dynamic/itis/s4l/simulator/neuron/sources": {
        key: "simcore/services/dynamic/itis/s4l/simulator/neuron/sources",
        version: "1.0.0",
        name: "Sources",
        inputsDefault: {
          defaultNeuronSources: {
            displayOrder: 0,
            label: "Default Sources Settings",
            description: "Default Sources Settings",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          mapper: {
            displayOrder: 0,
            label: "Sources Conditions",
            description: "Maps LF Fields into Sources",
            type: "mapper",
            maps: {
              leaf: "simcore/services/dynamic/itis/s4l/simulator/lf/sensors"
            }
          }
        }
      },
      "simcore/services/dynamic/itis/s4l/simulator/neuron/point": {
        key: "simcore/services/dynamic/itis/s4l/simulator/neuron/point",
        version: "1.0.0",
        name: "Point Processes",
        inputsDefault: {
          defaultNeuronPointProcesses: {
            displayOrder: 0,
            label: "Default Point Processes",
            description: "Default Point Processes",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          mapper: {
            displayOrder: 0,
            label: "Point Processes",
            description: "Maps Model entities into Point Processes",
            type: "mapper",
            maps: {
              leaf: "simcore/services/dynamic/modeler/webserver"
            }
          }
        }
      },
      "simcore/services/dynamic/itis/s4l/simulator/neuron/network": {
        key: "simcore/services/dynamic/itis/s4l/simulator/neuron/network",
        version: "1.0.0",
        name: "Network Connection",
        description: "Neuron Simulator Network Connection Settings",
        inputsDefault: {
          defaultNeuronNetworkConnection: {
            displayOrder: 0,
            label: "Default Network Connection",
            description: "Default Network Connection",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          mapper: {
            displayOrder: 0,
            label: "Network Connection",
            description: "Maps Model entities into Network Connection",
            type: "mapper",
            maps: {
              leaf: "simcore/services/dynamic/modeler/webserver"
            }
          }
        }
      },
      "simcore/services/dynamic/itis/s4l/simulator/neuron/sensors": {
        key: "simcore/services/dynamic/itis/s4l/simulator/neuron/sensors",
        version: "1.0.0",
        name: "Sensors",
        inputsDefault: {
          defaultNeuronSensors: {
            displayOrder: 0,
            label: "Default Sensors",
            description: "Default Sensors",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          mapper: {
            displayOrder: 0,
            label: "Sensors",
            description: "Maps Model entities into Sensors",
            type: "mapper",
            maps: {
              leaf: "simcore/services/dynamic/modeler/webserver"
            }
          }
        }
      },
      "simcore/services/dynamic/itis/s4l/simulator/neuron/solver": {
        key: "simcore/services/dynamic/itis/s4l/simulator/neuron/solver",
        version: "1.0.0",
        name: "Solver Settings",
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
        }
      },

      "defaultNeurons": {
        "SENN-UUID": {
          "restingPotential": {
            displayOrder: 0,
            label: "Resting Potential",
            unit: "mV",
            type: "number",
            defaultValue: -70
          },
          "activeSim": {
            displayOrder: 1,
            label: "Active for Simulation",
            unit: "",
            type: "boolean",
            defaultValue: true
          },
          "fiberDiameter": {
            displayOrder: 2,
            label: "Fiber Diameter",
            unit: "um",
            type: "number",
            defaultValue: 20
          }
        },
        "MOTOR-UUID": {
          "restingPotential": {
            displayOrder: 0,
            label: "Resting Potential",
            unit: "mV",
            type: "number",
            defaultValue: -80
          },
          "activeSim": {
            displayOrder: 1,
            label: "Active for Simulation",
            unit: "",
            type: "boolean",
            defaultValue: true
          },
          "fiberDiameter": {
            displayOrder: 2,
            label: "Fiber Diameter",
            unit: "um",
            type: "number",
            defaultValue: 5.7
          }
        },
        "RAT-UUID": {
          "restingPotential": {
            displayOrder: 0,
            label: "Resting Potential",
            unit: "mV",
            type: "number",
            defaultValue: -78
          },
          "activeSim": {
            displayOrder: 1,
            label: "Active for Simulation",
            unit: "",
            type: "boolean",
            defaultValue: true
          },
          "fiberDiameter": {
            displayOrder: 2,
            label: "Fiber Diameter",
            unit: "um",
            type: "number",
            defaultValue: 20
          }
        },
        "Sweeney-UUID": {
          "restingPotential": {
            displayOrder: 0,
            label: "Resting Potential",
            unit: "mV",
            type: "number",
            defaultValue: -80
          },
          "activeSim": {
            displayOrder: 1,
            label: "Active for Simulation",
            unit: "",
            type: "boolean",
            defaultValue: true
          },
          "fiberDiameter": {
            displayOrder: 2,
            label: "Fiber Diameter",
            unit: "um",
            type: "number",
            defaultValue: 20
          }
        },
        "Hoc-UUID": {
          "restingPotential": {
            displayOrder: 0,
            label: "Resting Potential",
            unit: "mV",
            type: "number",
            defaultValue: -70
          },
          "activeSim": {
            displayOrder: 1,
            label: "Active for Simulation",
            unit: "",
            type: "boolean",
            defaultValue: true
          },
          "hocFile": {
            displayOrder: 2,
            label: "Path to hoc file",
            unit: "",
            type: "string",
            defaultValue: ""
          },
          "useSchematic": {
            displayOrder: 3,
            label: "Use Schematic",
            unit: "",
            type: "boolean",
            defaultValue: true
          }
        }
      },

      "defaultNeuronSources": {
        "SourceSettings-UUID": {
          "pulseType": {
            displayOrder: 0,
            label: "Pulse Type",
            unit: "",
            type: "string",
            defaultValue: "Monopolar"
          },
          "initTime": {
            displayOrder: 1,
            label: "Initial Time",
            unit: "ms",
            type: "number",
            defaultValue: 0.1
          },
          "pulseAmplitude": {
            displayOrder: 2,
            label: "Pulse Amplitude",
            unit: "",
            type: "number",
            defaultValue: 1
          },
          "pulseDuration": {
            displayOrder: 3,
            label: "Pulse Duration",
            unit: "ms",
            type: "number",
            defaultValue: 0.1
          }
        }
      },

      "defaultNeuronPointProcesses": {
        "ExpSyn-UUID": {
          "sectionName": {
            displayOrder: 0,
            label: "Section Name",
            unit: "",
            type: "string",
            defaultValue: "-"
          },
          "relativePosition": {
            displayOrder: 1,
            label: "Relative Position",
            unit: "",
            type: "number",
            defaultValue: 0.5
          },
          "decayTime": {
            displayOrder: 2,
            label: "Decay Time",
            unit: "ms",
            type: "number",
            defaultValue: 0
          },
          "reversalPotential": {
            displayOrder: 3,
            label: "Reversal Potential",
            unit: "mV",
            type: "number",
            defaultValue: 0
          }
        },
        "Exp2Syn-UUID": {
          "sectionName": {
            displayOrder: 0,
            label: "Section Name",
            unit: "",
            type: "string",
            defaultValue: "-"
          },
          "relativePosition": {
            displayOrder: 1,
            label: "Relative Position",
            unit: "",
            type: "number",
            defaultValue: 0.5
          },
          "riseTime": {
            displayOrder: 2,
            label: "Rise Time",
            unit: "ms",
            type: "number",
            defaultValue: 0
          },
          "decayTime": {
            displayOrder: 3,
            label: "Decay Time",
            unit: "ms",
            type: "number",
            defaultValue: 0
          },
          "reversalPotential": {
            displayOrder: 4,
            label: "Reversal Potential",
            unit: "mV",
            type: "number",
            defaultValue: 0
          }
        },
        "AlphaSynapse-UUID": {
          "sectionName": {
            displayOrder: 0,
            label: "Section Name",
            unit: "",
            type: "string",
            defaultValue: "-"
          },
          "relativePosition": {
            displayOrder: 1,
            label: "Relative Position",
            unit: "",
            type: "number",
            defaultValue: 0.5
          },
          "onset": {
            displayOrder: 2,
            label: "Onset",
            unit: "ms",
            type: "number",
            defaultValue: 0
          },
          "decayTime": {
            displayOrder: 3,
            label: "Decay Time",
            unit: "ms",
            type: "number",
            defaultValue: 0
          },
          "maximumConductance": {
            displayOrder: 4,
            label: "Maximum Conductance",
            unit: "uS",
            type: "number",
            defaultValue: 0
          },
          "reversalPotential": {
            displayOrder: 5,
            label: "Reversal Potential",
            unit: "mV",
            type: "number",
            defaultValue: 0
          }
        },
        "IClamp-UUID": {
          "sectionName": {
            displayOrder: 0,
            label: "Section Name",
            unit: "",
            type: "string",
            defaultValue: "-"
          },
          "relativePosition": {
            displayOrder: 1,
            label: "Relative Position",
            unit: "",
            type: "number",
            defaultValue: 0.5
          },
          "delay": {
            displayOrder: 2,
            label: "Delay",
            unit: "ms",
            type: "number",
            defaultValue: 0
          },
          "duration": {
            displayOrder: 3,
            label: "Duration",
            unit: "ms",
            type: "number",
            defaultValue: 0
          },
          "amplitude": {
            displayOrder: 4,
            label: "Amplitude",
            unit: "nA",
            type: "number",
            defaultValue: 0
          }
        }
      },

      "defaultNeuronNetworkConnection": {
        "Synapse-UUID": {
          "sectionName": {
            displayOrder: 0,
            label: "Section Name",
            unit: "",
            type: "string",
            defaultValue: "-"
          },
          "relativePosition": {
            displayOrder: 1,
            label: "Relative Position",
            unit: "",
            type: "number",
            defaultValue: 0.5
          },
          "threshold": {
            displayOrder: 2,
            label: "Threshold",
            unit: "",
            type: "number",
            defaultValue: 0.5
          },
          "delay": {
            displayOrder: 3,
            label: "Delay",
            unit: "ms",
            type: "number",
            defaultValue: 0
          },
          "weight": {
            displayOrder: 4,
            label: "Weight",
            unit: "",
            type: "number",
            defaultValue: 0
          }
        }
      },

      "defaultNeuronSensors": {
        "Line-Sensor-UUID": {
          "measuredQuantity": {
            displayOrder: 0,
            label: "Measured Quantity",
            unit: "",
            type: "string",
            defaultValue: "V"
          },
          "numberSnapshots": {
            displayOrder: 1,
            label: "Number of Snapshots",
            unit: "",
            type: "number",
            defaultValue: 1
          }
        },
        "Point-Sensor-UUID": {
          "sectionName": {
            displayOrder: 0,
            label: "Section Name",
            unit: "",
            type: "string",
            defaultValue: "-"
          },
          "relativePosition": {
            displayOrder: 1,
            label: "Relative Position",
            unit: "",
            type: "number",
            defaultValue: 0.5
          },
          "measuredQuantity": {
            displayOrder: 2,
            label: "Measured Quantity",
            unit: "",
            type: "string",
            defaultValue: "V"
          },
          "enableGrouping": {
            displayOrder: 3,
            label: "Enable Grouping",
            unit: "",
            type: "boolean",
            defaultValue: false
          }
        }
      }
    },

    getItemList: function(simSettingsId) {
      return qxapp.dev.fake.neuron.Data.itemList[simSettingsId];
    },

    getItem: function(simSettingsId, itemId) {
      if (itemId === undefined) {
        return qxapp.dev.fake.neuron.Data.item[simSettingsId];
      }
      return qxapp.dev.fake.neuron.Data.item[simSettingsId][itemId];
    },

    checkCompatiblity: function(settingKey, fromNodeKey, fromItemKey) {
      return true;
    }
  } // statics

});
