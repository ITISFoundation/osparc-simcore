qx.Class.define("qxapp.dev.fake.lf.Data", {
  type: "static",

  statics: {
    itemList: {
      "simcore/services/dynamic/itis/s4l/simulator/lf": [{
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/setup",
        label: "Setup"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/materials",
        label: "Materials"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/boundary",
        label: "Boundary Conditions"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/sensors",
        label: "Sensors"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/grid",
        label: "Grid"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/voxel",
        label: "Voxels"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/solver",
        label: "Solver"
      }],

      "defaultLFMaterials": [{
        key: "Air-UUID",
        label: "Air"
      }, {
        key: "Dielectric-UUID",
        label: "Dielectric"
      }, {
        key: "PEC-UUID",
        label: "PEC"
      }, {
        key: "PMC-UUID",
        label: "PMC"
      }],

      "defaultLFBoundaries": [{
        key: "Dirichlet-UUID",
        label: "Dirichlet"
      }, {
        key: "Neumann-UUID",
        label: "Neumann"
      }, {
        key: "Flux-UUID",
        label: "Flux"
      }],

      "defaultLFSensors": [{
        key: "Field-Sensor-UUID",
        label: "Field-Sensor"
      }, {
        key: "Voltage-Sensor-UUID",
        label: "Voltage-Sensor"
      }],

      "sensorSettingAPI": [{
        key: "Field-Sensor-UUID",
        label: "LF Field-Sensor (Overall Field)"
      }]
    },

    item: {
      "simcore/services/dynamic/itis/s4l/simulator/lf/setup": {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/setup",
        version: "1.0.0",
        name: "LF Setup",
        inputs: {
          frequency: {
            displayOrder: 0,
            label: "Frequency",
            description: "Frequency (Hz)",
            type: "number",
            defaultValue: 1000
          }
        }
      },

      "simcore/services/dynamic/itis/s4l/simulator/lf/materials": {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/materials",
        version: "1.0.0",
        name: "LF Materials",
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
          mapper: {
            displayOrder: 1,
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
        }
      },

      "simcore/services/dynamic/itis/s4l/simulator/lf/boundary": {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/boundary",
        version: "1.0.0",
        name: "LF Boundary Conditions",
        inputsDefault: {
          defaultLFBoundaries: {
            displayOrder: 0,
            label: "Default Boundary Settings",
            description: "Default Boundary Settings",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          mapper: {
            displayOrder: 0,
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
        }
      },

      "simcore/services/dynamic/itis/s4l/simulator/lf/sensors": {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/sensors",
        version: "1.0.0",
        name: "LF Sensors",
        inputsDefault: {
          defaultLFSensors: {
            displayOrder: 0,
            label: "Default Sensors",
            description: "Default Sensors",
            type: "node-output-tree-api-v0.0.1"
          }
        },
        inputs: {
          mapper: {
            displayOrder: 0,
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
          sensorSettingAPI: {
            displayOrder: 0,
            label: "LF Sensors",
            description: "LF Sensors",
            type: "node-output-tree-api-v0.0.1"
          }
        }
      },

      "simcore/services/dynamic/itis/s4l/simulator/lf/grid": {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/grid",
        version: "1.0.0",
        name: "LF Grid",
        description: "LF Simulator Grid Settings",
        inputs: {
          homogeneous: {
            displayOrder: 0,
            label: "Homogeneous grid",
            description: "Homogeneous grid",
            type: "boolean",
            defaultValue: true
          },
          resolution: {
            displayOrder: 1,
            label: "Resolution (mm)",
            description: "Resolution in mm",
            type: "number",
            defaultValue: 1
          }
        }
      },

      "simcore/services/dynamic/itis/s4l/simulator/lf/voxel": {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/voxel",
        version: "1.0.0",
        name: "LF Voxels",
        description: "LF Simulator Voxel Settings",
        inputs: {
          voxelEngine: {
            displayOrder: 0,
            label: "Used Voxel Engine",
            description: "Used Voxel Engine",
            type: "string",
            defaultValue: "Topological Voxeler"
          },
          maximumFraction: {
            displayOrder: 1,
            label: "Maximum Fraction",
            description: "Maximum Fraction",
            type: "number",
            defaultValue: 21
          },
          congruentSubgrid: {
            displayOrder: 2,
            label: "Congruent Subgrid Voxeling",
            description: "Congruent Subgrid Voxeling",
            type: "boolean",
            defaultValue: true
          }
        }
      },

      "simcore/services/dynamic/itis/s4l/simulator/lf/solver": {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/solver",
        version: "1.0.0",
        name: "LF Solver Settings",
        description: "LF Simulator Solver Settings",
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
        }
      },

      "defaultLFMaterials": {
        "Air-UUID": {
          "massDensity": {
            "displayOrder": 0,
            "label": "Mass Density",
            "unit": "kg/m^3",
            "type": "number",
            "defaultValue": 1.205
          },
          "electricConductivity": {
            "displayOrder": 1,
            "label": "Electric Conductivity",
            "unit": "S/m",
            "type": "number",
            "defaultValue": 0.0
          },
          "relativePermittivity": {
            "displayOrder": 2,
            "label": "Relative Permittivity",
            "unit": "",
            "type": "number",
            "defaultValue": 1.0
          },
          "magneticConductivity": {
            "displayOrder": 3,
            "label": "Magnetic Conductivity",
            "unit": "Ohm/m",
            "type": "number",
            "defaultValue": 0.0
          },
          "relativePermeability": {
            "displayOrder": 4,
            "label": "Relative Permeability",
            "unit": "",
            "type": "number",
            "defaultValue": 1.0
          }
        },
        "Dielectric-UUID": {
          "massDensity": {
            displayOrder: 0,
            label: "Mass Density",
            unit: "kg/m3",
            type: "number",
            defaultValue: 1000
          },
          "electricConductivity": {
            displayOrder: 1,
            label: "Electric Conductivity",
            unit: "S/m",
            type: "number",
            defaultValue: 0
          },
          "electricRelativePermitivity": {
            displayOrder: 2,
            label: "Electric Relative Permittivity",
            unit: "",
            type: "number",
            defaultValue: 1
          },
          "magneticRelativePermeability": {
            displayOrder: 3,
            label: "Magnetic Relative Permeability",
            unit: "",
            type: "number",
            defaultValue: 1
          },
          "magneticConductivity": {
            displayOrder: 4,
            label: "Magnetic Conductivity",
            unit: "Ohm/m",
            type: "number",
            defaultValue: 0
          }
        }
      },

      "defaultLFBoundaries": {
        "Dirichlet-UUID": {
          "constantPotential": {
            displayOrder: 0,
            label: "Constant Potential",
            unit: "V",
            type: "number",
            defaultValue: 0
          },
          "phase": {
            displayOrder: 1,
            label: "Phase",
            unit: "deg",
            type: "number",
            defaultValue: 0
          }
        },
        "Neumann-UUID": {
          "normalDerivative": {
            displayOrder: 0,
            label: "Normal Derivative",
            unit: "V/m",
            type: "number",
            defaultValue: 0
          },
          "phase": {
            displayOrder: 1,
            label: "Phase",
            unit: "deg",
            type: "number",
            defaultValue: 0
          }
        },
        "Flux-UUID": {
          "constantFlux": {
            displayOrder: 0,
            label: "Constant Flux",
            unit: "",
            type: "number",
            defaultValue: 0
          },
          "phase": {
            displayOrder: 1,
            label: "Phase",
            unit: "deg",
            type: "number",
            defaultValue: 0
          }
        }
      },

      "defaultLFSensors": {
        "Field-Sensor-UUID": {
          "recordEField": {
            displayOrder: 0,
            label: "Record E-Field",
            unit: "",
            type: "boolean",
            defaultValue: true
          },
          "recordHField": {
            displayOrder: 1,
            label: "Record H-Field",
            unit: "",
            type: "boolean",
            defaultValue: true
          },
          "recordMagnetic": {
            displayOrder: 3,
            label: "Record Magnetic Vector-Potential-Field",
            unit: "",
            type: "boolean",
            defaultValue: true
          }
        },
        "Voltage-Sensor-UUID": {
          "revertDirection": {
            displayOrder: 0,
            label: "Revert Direction",
            unit: "",
            type: "boolean",
            defaultValue: false
          }
        }
      }
    },

    getItemList: function(simSettingsId) {
      return qxapp.dev.fake.lf.Data.itemList[simSettingsId];
    },

    getItem: function(simSettingsId, itemId) {
      if (itemId === undefined) {
        return qxapp.dev.fake.lf.Data.item[simSettingsId];
      }
      return qxapp.dev.fake.lf.Data.item[simSettingsId][itemId];
    }
  } // statics
});
