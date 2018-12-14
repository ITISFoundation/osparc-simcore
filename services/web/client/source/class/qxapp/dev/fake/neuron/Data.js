qx.Class.define("qxapp.dev.fake.neuron.Data", {
  type: "static",

  statics: {
    itemList: {
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

    compare: function(a, b) {
      if (a.label < b.label) {
        return -1;
      }
      if (a.label > b.label) {
        return 1;
      }
      return 0;
    },

    getItemList: function(simSettingsId) {
      let itemList = qxapp.dev.fake.neuron.Data.itemList[simSettingsId];
      if (itemList) {
        itemList.sort(this.compare);
      }
      return itemList;
    },

    getItem: function(simSettingsId, itemId) {
      return qxapp.dev.fake.neuron.Data.item[simSettingsId][itemId];
    }
  } // statics

});
