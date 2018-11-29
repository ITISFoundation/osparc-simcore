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

      "defaultSources": [{
        key: "SourceSettings-UUID",
        label: "Source Settings"
      }],

      "defaultPointProcesses": [{
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
      }, {
        key: "VClamp-UUID",
        label: "VClamp"
      }],

      "defaultNetworkConnection": [{
        key: "Synapse-UUID",
        label: "Synapse"
      }],

      "defaultSensors": [{
        key: "Line-Sensor-UUID",
        label: "Line-Sensor"
      }, {
        key: "Point-Sensor-UUID",
        label: "Point-Sensor"
      }]
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

      "defaultSources": {
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

    getItemList: function() {
      let itemList = qxapp.dev.fake.neuron.Data.itemList;
      itemList.sort(this.compare);
      return itemList;
    }
  } // statics

});
