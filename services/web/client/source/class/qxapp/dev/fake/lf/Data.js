qx.Class.define("qxapp.dev.fake.lf.Data", {
  type: "static",

  statics: {
    itemList: {
      "simcore/services/dynamic/itis/s4l/simulator/lf": [{
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/setup",
        version: "1.0.0"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/materials",
        version: "1.0.0"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/boundary",
        version: "1.0.0"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/sensors",
        version: "1.0.0"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/grid",
        version: "1.0.0"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/voxel",
        version: "1.0.0"
      }, {
        key: "simcore/services/dynamic/itis/s4l/simulator/lf/solver",
        version: "1.0.0"
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

      "defaultLFGrids": [{
        key: "Automatic-Grid-UUID",
        label: "Automatic"
      }, {
        key: "Manual-Grid-UUID",
        label: "Manual"
      }],

      "defaultLFVoxels": [{
        key: "Automatic-Voxel-UUID",
        label: "Automatic"
      }, {
        key: "Manual-Voxel-UUID",
        label: "Manual"
      }],

      "sensorSettingAPI": [{
        key: "Field-Sensor-UUID",
        label: "LF Field-Sensor (Overall Field)"
      }]
    },

    item: {
      "simcore/services/dynamic/itis/s4l/simulator/lf/setup": {
        "root": {
          key: "simcore/services/dynamic/itis/s4l/simulator/lf/setup",
          version: "1.0.0",
          name: "Setup",
          inputs: {
            frequency: {
              displayOrder: 0,
              label: "Frequency",
              description: "Frequency (Hz)",
              type: "number",
              defaultValue: 1000
            }
          }
        }
      },

      "simcore/services/dynamic/itis/s4l/simulator/lf/materials": {
        "root": {
          key: "simcore/services/dynamic/itis/s4l/simulator/lf/materials",
          version: "1.0.0",
          name: "Materials",
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
              defaultValue: {
                "Air-UUID": [
                  "Background-UUID"
                ]
              }
            }
          }
        },
        "Air-UUID": {
          key: "Air-UUID",
          version: "1.0.0",
          name: "Air",
          inputs: {
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
          }
        },
        "Dielectric-UUID": {
          key: "Dielectric-UUID",
          version: "1.0.0",
          name: "Dielectric",
          inputs: {
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
        }
      },

      "simcore/services/dynamic/itis/s4l/simulator/lf/boundary": {
        "root": {
          key: "simcore/services/dynamic/itis/s4l/simulator/lf/boundary",
          version: "1.0.0",
          name: "Boundary Conditions",
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
              defaultValue: {
                "Dirichlet-UUID": [
                  "Plane X+-UUID",
                  "Plane X--UUID",
                  "Plane Y+-UUID",
                  "Plane Y--UUID",
                  "Plane Z+-UUID",
                  "Plane Z--UUID"
                ]
              }
            }
          }
        },
        "Dirichlet-UUID": {
          key: "Dirichlet-UUID",
          version: "1.0.0",
          name: "Dirichlet",
          inputs: {
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
          }
        },
        "Neumann-UUID": {
          key: "Neumann-UUID",
          version: "1.0.0",
          name: "Neumann",
          inputs: {
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
          }
        },
        "Flux-UUID": {
          key: "Flux-UUID",
          version: "1.0.0",
          name: "Flux",
          inputs: {
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
        }
      },

      "simcore/services/dynamic/itis/s4l/simulator/lf/sensors": {
        "root": {
          key: "simcore/services/dynamic/itis/s4l/simulator/lf/sensors",
          version: "1.0.0",
          name: "Sensors",
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
              defaultValue: {
                "Field-Sensor-UUID": [
                  "Overall Field-UUID"
                ]
              }
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
        "Field-Sensor-UUID": {
          key: "Field-Sensor-UUID",
          version: "1.0.0",
          name: "Field Sensor",
          inputs: {
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
          }
        },
        "Voltage-Sensor-UUID": {
          key: "Voltage-Sensor-UUID",
          version: "1.0.0",
          name: "Voltage Sensor",
          inputs: {
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

      "simcore/services/dynamic/itis/s4l/simulator/lf/grid": {
        "root": {
          key: "simcore/services/dynamic/itis/s4l/simulator/lf/grid",
          version: "1.0.0",
          name: "Grid",
          inputsDefault: {
            defaultLFGrids: {
              displayOrder: 0,
              label: "Default Grid Settings",
              description: "Default Grid Settings",
              type: "node-output-tree-api-v0.0.1"
            }
          },
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
            },
            mapper: {
              displayOrder: 2,
              label: "Grid",
              description: "Grid",
              type: "mapper",
              maps: {
                leaf: "simcore/services/dynamic/modeler/webserver"
              },
              defaultValue: {
                "Automatic-Grid-UUID": []
              }
            }
          }
        },
        "Automatic-Grid-UUID": {
          key: "Automatic-Grid-UUID",
          version: "1.0.0",
          name: "Automatic Grid",
          inputs: {
            "refinment": {
              displayOrder: 0,
              label: "Refinment",
              unit: "",
              type: "string",
              defaultValue: "Default"
            },
            "groupName": {
              displayOrder: 1,
              label: "Group Name",
              unit: "",
              type: "string",
              defaultValue: ""
            }
          }
        },
        "Manual-Grid-UUID": {
          key: "Manual-Grid-UUID",
          version: "1.0.0",
          name: "Manual Grid",
          inputs: {
            "maxStep": {
              displayOrder: 0,
              label: "Maximum Step",
              unit: "mm",
              type: "number",
              defaultValue: 1
            },
            "geomRes": {
              displayOrder: 1,
              label: "Geometry Resolution",
              unit: "mm",
              type: "number",
              defaultValue: 1
            },
            "priority": {
              displayOrder: 2,
              label: "Priority",
              unit: "",
              type: "number",
              defaultValue: 50
            }
          }
        }
      },

      "simcore/services/dynamic/itis/s4l/simulator/lf/voxel": {
        "root": {
          key: "simcore/services/dynamic/itis/s4l/simulator/lf/voxel",
          version: "1.0.0",
          name: "Voxels",
          inputsDefault: {
            defaultLFVoxels: {
              displayOrder: 0,
              label: "Default Voxel Settings",
              description: "Default Voxel Settings",
              type: "node-output-tree-api-v0.0.1"
            }
          },
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
            },
            mapper: {
              displayOrder: 3,
              label: "Voxel",
              description: "Voxel",
              type: "mapper",
              maps: {
                leaf: "simcore/services/dynamic/modeler/webserver"
              },
              defaultValue: {
                "Automatic-Voxel-UUID": []
              }
            }
          }
        },
        "Automatic-Voxel-UUID": {
          key: "Automatic-Voxel-UUID",
          version: "1.0.0",
          name: "Automatic Voxel",
          inputs: {
            "priority": {
              displayOrder: 0,
              label: "Priority",
              unit: "",
              type: "number",
              defaultValue: 0
            },
            "useCons": {
              displayOrder: 1,
              label: "Use Constraints",
              unit: "",
              type: "boolean",
              defaultValue: false
            }
          }
        },
        "Manual-Voxel-UUID": {
          key: "Manual-Voxel-UUID",
          version: "1.0.0",
          name: "Manual Voxel",
          inputs: {
            "priority": {
              displayOrder: 0,
              label: "Priority",
              unit: "",
              type: "number",
              defaultValue: 0
            },
            "region": {
              displayOrder: 1,
              label: "Characteristic Region",
              unit: "",
              type: "string",
              defaultValue: "Volume"
            },
            "maxNormDist": {
              displayOrder: 2,
              label: "Max Normal Distance",
              unit: "",
              type: "number",
              defaultValue: 100
            },
            "useConstraints": {
              displayOrder: 3,
              label: "Use Constraints",
              unit: "",
              type: "boolean",
              defaultValue: false
            }
          }
        }
      },

      "simcore/services/dynamic/itis/s4l/simulator/lf/solver": {
        "root": {
          key: "simcore/services/dynamic/itis/s4l/simulator/lf/solver",
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
        }
      }
    },

    getItemList: function(simSettingsId) {
      return qxapp.dev.fake.lf.Data.itemList[simSettingsId];
    },

    getItem: function(simSettingsId, itemId) {
      if (itemId === undefined) {
        itemId = "root";
      }
      return qxapp.dev.fake.lf.Data.item[simSettingsId][itemId];
    },

    checkCompatibility: function(settingKey, fromNodeKey, fromItemKey) {
      return true;
    }
  } // statics
});
