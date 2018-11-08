qx.Class.define("qxapp.data.Store", {
  extend: qx.core.Object,

  type : "singleton",

  events: {
    "servicesRegistered": "qx.event.type.Event"
  },

  statics: {
    /**
     * Represents an empty project descriptor
    */
    NEW_PROJECT_DESCRIPTOR: qx.data.marshal.Json.createModel({
      name: "New Project",
      description: "Empty",
      thumbnail: "https://imgplaceholder.com/171x96/cccccc/757575/ion-plus-round",
      created: new Date(),
      projectId: qxapp.utils.Utils.uuidv4()
    })
  },

  members: {
    __servicesCache: null,

    __getMimeType: function(type) {
      let match = type.match(/^data:([^/\s]+\/[^/;\s])/);
      if (match) {
        return match[1];
      }
      return null;
    },

    __matchPortType: function(typeA, typeB) {
      if (typeA === typeB) {
        return true;
      }
      let mtA = this.__getMimeType(typeA);
      let mtB = this.__getMimeType(typeB);
      return mtA && mtB &&
        new qxapp.data.MimeType(mtA).match(new qxapp.data.MimeType(mtB));
    },

    areNodesCompatible: function(topLevelPort1, topLevelPort2) {
      console.log("areNodesCompatible", topLevelPort1, topLevelPort2);
      return topLevelPort1.isInput !== topLevelPort2.isInput;
    },

    arePortsCompatible: function(node1, port1, node2, port2) {
      console.log("arePortsCompatible", node1, port1, node2, port2);
      return true;
      /*
      return this.__matchPortType(port1.portType, port2.portType) &&
        (port1.isInput !== port2.isInput);
      */
    },

    getUserProjectList: function() {
      return qxapp.dev.fake.Data.getUserProjectList();
    },

    getPublicProjectList: function() {
      return qxapp.dev.fake.Data.getPublicProjectList();
    },

    getProjectList: function() {
      return qxapp.dev.fake.Data.getProjectList();
    },

    getProjectData: function(projectUuid) {
      return qxapp.dev.fake.Data.getProjectData(projectUuid);
    },

    getNodeMetaData: function(key, version) {
      let metaData = {};
      if (key && version) {
        const nodeImageId = key + "-" + version;
        if (nodeImageId in this.__servicesCache) {
          return this.__servicesCache[nodeImageId];
        }
        metaData = this.getFakeServices()[nodeImageId];
        if (metaData === undefined) {
          metaData = this.getBuiltInServices()[nodeImageId];
        }
      }
      return metaData;
    },

    getItemList: function(nodeInstanceUUID, portKey) {
      switch (portKey) {
        case "defaultNeuromanModels":
          return [{
            key: "Yoon-sun-UUID",
            label: "Yoon-sun",
            thumbnail: "qxapp/yoonsun.png"
          }, {
            key: "Yoon-sun-Light-UUID",
            label: "Yoon-sun Light",
            thumbnail: "qxapp/yoonsun-light.png"
          }, {
            key: "Rat-UUID",
            label: "Rat",
            thumbnail: "qxapp/rat.png"
          }, {
            key: "Rat-Light-UUID",
            label: "Rat Light",
            thumbnail: "qxapp/rat-light.png"
          }];
        case "defaultMaterials":
          return [{
            key: "Dielectric-UUID",
            label: "Dielectric"
          }, {
            key: "PEC-UUID",
            label: "PEC"
          }, {
            key: "PMC-UUID",
            label: "PMC"
          }];
        case "defaultBoundaries":
          return [{
            key: "Dirichlet-UUID",
            label: "Dirichlet"
          }, {
            key: "Neumann-UUID",
            label: "Neumann"
          }, {
            key: "Flux-UUID",
            label: "Flux"
          }];
        case "modeler":
          return [{
            key: "MODEL1-UUID",
            label: "Model 1"
          }, {
            key: "MODEL2-UUID",
            label: "Model 2"
          }, {
            key: "MODEL3-UUID",
            label: "Model 3"
          }];
        case "materialDB":
          return [{
            key: "Air-UUID",
            label: "Air"
          }, {
            key: "Brain-UUID",
            label: "Brain"
          }, {
            key: "Eye-UUID",
            label: "Eye"
          }];
        case "defaultStimulationSelectivity":
          return [{
            key: "StSeSubgroup-UUID",
            label: "Subgroup"
          }];
      }
      return [];
    },

    getItem: function(nodeInstanceUUID, portKey, itemUuid) {
      switch (portKey) {
        case "materialDB": {
          switch (itemUuid) {
            case "Air-UUID": {
              return {
                "massDensity": {
                  displayOrder: 0,
                  label: "Mass Density",
                  unit: "kg/m3",
                  type: "number",
                  defaultValue: 1.16409
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
                "magneticConductivity": {
                  displayOrder: 3,
                  label: "Magnetic Conductivity",
                  unit: "Ohm/m",
                  type: "number",
                  defaultValue: 0
                },
                "magneticRelativePermeability": {
                  displayOrder: 4,
                  label: "Magnetic Relative Permeability",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                }
              };
            }
            case "Brain-UUID": {
              return {
                "massDensity": {
                  displayOrder: 0,
                  label: "Mass Density",
                  unit: "kg/m3",
                  type: "number",
                  defaultValue: 1045.5
                },
                "electricConductivity": {
                  displayOrder: 1,
                  label: "Electric Conductivity",
                  unit: "S/m",
                  type: "number",
                  defaultValue: 0.234007
                },
                "electricRelativePermitivity": {
                  displayOrder: 2,
                  label: "Electric Relative Permittivity",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                },
                "magneticConductivity": {
                  displayOrder: 3,
                  label: "Magnetic Conductivity",
                  unit: "Ohm/m",
                  type: "number",
                  defaultValue: 0
                },
                "magneticRelativePermeability": {
                  displayOrder: 4,
                  label: "Magnetic Relative Permeability",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                }
              };
            }
            case "Eye-UUID": {
              return {
                "massDensity": {
                  displayOrder: 0,
                  label: "Mass Density",
                  unit: "kg/m3",
                  type: "number",
                  defaultValue: 1050.5
                },
                "electricConductivity": {
                  displayOrder: 1,
                  label: "Electric Conductivity",
                  unit: "S/m",
                  type: "number",
                  defaultValue: 0.62
                },
                "electricRelativePermitivity": {
                  displayOrder: 2,
                  label: "Electric Relative Permittivity",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                },
                "magneticConductivity": {
                  displayOrder: 3,
                  label: "Magnetic Conductivity",
                  unit: "Ohm/m",
                  type: "number",
                  defaultValue: 0
                },
                "magneticRelativePermeability": {
                  displayOrder: 4,
                  label: "Magnetic Relative Permeability",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                }
              };
            }
          }
        }
        // eslint-disable-next-line no-fallthrough
        case "defaultMaterials": {
          switch (itemUuid) {
            case "Dielectric-UUID": {
              return {
                "massDensity": {
                  displayOrder: 0,
                  label: "Mass Density",
                  unit: "kg/m3",
                  type: "number",
                  defaultValue: 1.205
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
              };
            }
          }
        }
      }
      return {};
    },

    getList: function(nodeImageId) {
      switch (nodeImageId) {
        // case "services/demodec/dynamic/itis/s4l/Modeler-0.0.0": {
        case "data:application/s4l-api/modeler": {
          return [
            {
              name: "Model 1",
              uuid: "MODEL1-UUID",
              properties: {}
            }, {
              name: "Model 2",
              uuid: "MODEL2-UUID",
              properties: {}
            }, {
              name: "Model 3",
              uuid: "MODEL3-UUID",
              properties: {}
            }, {
              name: "Model 4",
              uuid: "MODEL4-UUID",
              properties: {}
            }
          ];
        }
        // case "services/demodec/dynamic/itis/s4l/MaterialDB-0.0.0": {
        case "data:application/s4l-api/materialDB": {
          return [
            {
              name: "Air",
              uuid: "Air-UUID",
              properties: {
                "massDensity": {
                  displayOrder: 0,
                  label: "Mass Density",
                  unit: "kg/m3",
                  type: "number",
                  defaultValue: 1.16409
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
                "magneticConductivity": {
                  displayOrder: 3,
                  label: "Magnetic Conductivity",
                  unit: "Ohm/m",
                  type: "number",
                  defaultValue: 0
                },
                "magneticRelativePermeability": {
                  displayOrder: 4,
                  label: "Magnetic Relative Permeability",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                }
              }
            }, {
              name: "Brain",
              uuid: "Brain-UUID",
              properties: {
                "massDensity": {
                  displayOrder: 0,
                  label: "Mass Density",
                  unit: "kg/m3",
                  type: "number",
                  defaultValue: 1045.5
                },
                "electricConductivity": {
                  displayOrder: 1,
                  label: "Electric Conductivity",
                  unit: "S/m",
                  type: "number",
                  defaultValue: 0.234007
                },
                "electricRelativePermitivity": {
                  displayOrder: 2,
                  label: "Electric Relative Permittivity",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                },
                "magneticConductivity": {
                  displayOrder: 3,
                  label: "Magnetic Conductivity",
                  unit: "Ohm/m",
                  type: "number",
                  defaultValue: 0
                },
                "magneticRelativePermeability": {
                  displayOrder: 4,
                  label: "Magnetic Relative Permeability",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                }
              }
            }, {
              name: "Eye",
              uuid: "Eye-UUID",
              properties: {
                "massDensity": {
                  displayOrder: 0,
                  label: "Mass Density",
                  unit: "kg/m3",
                  type: "number",
                  defaultValue: 1050.5
                },
                "electricConductivity": {
                  displayOrder: 1,
                  label: "Electric Conductivity",
                  unit: "S/m",
                  type: "number",
                  defaultValue: 0.62
                },
                "electricRelativePermitivity": {
                  displayOrder: 2,
                  label: "Electric Relative Permittivity",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                },
                "magneticConductivity": {
                  displayOrder: 3,
                  label: "Magnetic Conductivity",
                  unit: "Ohm/m",
                  type: "number",
                  defaultValue: 0
                },
                "magneticRelativePermeability": {
                  displayOrder: 4,
                  label: "Magnetic Relative Permeability",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                }
              }
            }
          ];
        }
        case "services/demodec/dynamic/itis/s4l/Simulator/LF/Materials-0.0.0": {
          return [
            {
              name: "PEC",
              uuid: "PEC-UUID",
              properties: {}
            }, {
              name: "PMC",
              uuid: "PMC-UUID",
              properties: {}
            }, {
              name: "Dielectric",
              uuid: "Dielectric-UUID",
              properties: {
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
                "magneticConductivity": {
                  displayOrder: 3,
                  label: "Magnetic Conductivity",
                  unit: "Ohm/m",
                  type: "number",
                  defaultValue: 0
                },
                "magneticRelativePermeability": {
                  displayOrder: 4,
                  label: "Magnetic Relative Permeability",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                }
              }
            }
          ];
        }
        case "services/demodec/dynamic/itis/s4l/Simulator/LF/Boundary-0.0.0": {
          return [
            {
              name: "Dirichlet",
              uuid: "Dirichlet-UUID",
              properties: {
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
            }, {
              name: "Neumann",
              uuid: "Neumann-UUID",
              properties: {
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
            }, {
              name: "Flux",
              uuid: "Flux-UUID",
              properties: {
                "constantFlux": {
                  displayOrder: 0,
                  label: "Constant Flux",
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
          ];
        }
      }
      return [];
    },

    getBuiltInServices: function() {
      let builtInServices = {
        "services/dynamic/itis/file-picker-0.0.0": {
          key: "services/dynamic/itis/file-picker",
          version: "0.0.0",
          type: "computational",
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
        },
        "services/demodec/dynamic/itis/s4l/Neuroman-0.0.0": {
          key: "services/demodec/dynamic/itis/s4l/Neuroman",
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
              type: "node-output-list-icon-api-v0.0.1"
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
              type: "node-output-list-api-v0.0.1"
            }
          }
        },
        "services/demodec/dynamic/itis/s4l/StimulationSelectivity-0.0.0": {
          key: "services/demodec/dynamic/itis/s4l/StimulationSelectivity",
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
              type: "node-output-list-api-v0.0.1"
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
                leaf: "services/demodec/dynamic/itis/s4l/Modeler"
              }
            }
          },
          outputs: {
            modeler: {
              displayOrder: 0,
              label: "Stimulation factor",
              description: "Stimulation factor",
              type: "number"
            }
          }
        },
        "services/demodec/dynamic/itis/s4l/Modeler-0.0.0": {
          key: "services/demodec/dynamic/itis/s4l/Modeler",
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
              type: "node-output-list-api-v0.0.1"
            }
          }
        },
        "services/demodec/dynamic/itis/s4l/MaterialDB-0.0.0": {
          key: "services/demodec/dynamic/itis/s4l/MaterialDB",
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
              type: "node-output-list-api-v0.0.1"
            }
          }
        },
        "services/container/itis/s4l/Simulator/LF-0.0.0": {
          key: "services/container/itis/s4l/Simulator/LF",
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
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Setup",
              version: "0.0.0",
              inputNodes: [],
              outputNode: false
            },
            "inner2": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Materials",
              version: "0.0.0",
              inputNodes: [
                "modeler",
                "materialDB"
              ],
              outputNode: false
            },
            "inner3": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Boundary",
              version: "0.0.0",
              inputNodes: [
                "modeler"
              ],
              outputNode: false
            },
            "inner4": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Sensors",
              version: "0.0.0",
              inputNodes: [
                "modeler"
              ],
              outputNode: false
            },
            "inner5": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Grid",
              version: "0.0.0",
              inputNodes: [
                "modeler"
              ],
              outputNode: false
            },
            "inner6": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Voxel",
              version: "0.0.0",
              inputNodes: [
                "modeler"
              ],
              outputNode: false
            },
            "inner7": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/SolverSettings",
              version: "0.0.0",
              inputNodes: [],
              outputNode: true
            }
          }
        },
        "services/demodec/dynamic/itis/s4l/Simulator/LF/Setup-0.0.0": {
          key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Setup",
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
        },
        "services/demodec/dynamic/itis/s4l/Simulator/LF/Materials-0.0.0": {
          key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Materials",
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
            defaultMaterials: {
              displayOrder: 0,
              label: "Default Material Settings",
              description: "Default Material Settings",
              type: "node-output-list-api-v0.0.1"
            }
          },
          inputs: {
            updateDispersive: {
              displayOrder: 0,
              label: "UpdateDispersive",
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
                branch: "services/demodec/dynamic/itis/s4l/MaterialDB",
                leaf: "services/demodec/dynamic/itis/s4l/Modeler"
              }
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
        },
        "services/demodec/dynamic/itis/s4l/Simulator/LF/Boundary-0.0.0": {
          key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Boundary",
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
            defaultBoundaries: {
              displayOrder: 0,
              label: "Default Boundary Settings",
              description: "Default Boundary Settings",
              type: "node-output-list-api-v0.0.1"
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
                leaf: "services/demodec/dynamic/itis/s4l/Modeler"
              }
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
        },
        "services/demodec/dynamic/itis/s4l/Simulator/LF/Sensors-0.0.0": {
          key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Sensors",
          version: "0.0.0",
          type: "computational",
          name: "LF Sensors",
          description: "LF Simulator Sensors Settings",
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
            sensorSetting: {
              displayOrder: 1,
              label: "SensorsSettings",
              description: "Sensors Settings",
              type: "number",
              defaultValue: 4
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
              label: "SensorSettingsAPI",
              description: "Sensors",
              type: "data:application/s4l-api/sensor-settings"
            }
          }
        },
        "services/demodec/dynamic/itis/s4l/Simulator/LF/Grid-0.0.0": {
          key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Grid",
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
            materialSetting: {
              displayOrder: 1,
              label: "MaterialSettings",
              description: "Material Settings",
              type: "data:application/s4l-api/settings"
            },
            boundarySetting: {
              displayOrder: 2,
              label: "BoundarySettings",
              description: "Boundary Settings",
              type: "data:application/s4l-api/settings"
            },
            sensorSetting: {
              displayOrder: 3,
              label: "SensorSettings",
              description: "Sensor Settings",
              type: "data:application/s4l-api/settings"
            },
            gridSetting: {
              displayOrder: 4,
              label: "GridSettings",
              description: "Grid Settings",
              type: "number",
              defaultValue: 5
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
        },
        "services/demodec/dynamic/itis/s4l/Simulator/LF/Voxel-0.0.0": {
          key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Voxel",
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
            gridSetting: {
              displayOrder: 1,
              label: "GridSettings",
              description: "Grid Settings",
              type: "data:application/s4l-api/settings"
            },
            voxelSetting: {
              displayOrder: 2,
              label: "VoxelSettings",
              description: "Voxel Settings",
              type: "number",
              defaultValue: 6
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
        },
        "services/demodec/dynamic/itis/s4l/Simulator/LF/SolverSettings-0.0.0": {
          key: "services/demodec/dynamic/itis/s4l/Simulator/LF/SolverSettings",
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
            setupSetting: {
              displayOrder: 0,
              label: "SetupSettings",
              description: "Setup Settings Out",
              type: "data:application/s4l-api/settings"
            },
            voxelSetting: {
              displayOrder: 1,
              label: "VoxelSettings",
              description: "Voxel Settings",
              type: "data:application/s4l-api/settings"
            },
            solverSetting: {
              displayOrder: 2,
              label: "SolverSetting",
              description: "Solver Setting",
              type: "number",
              defaultValue: 7
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
        },
        "services/computational/itis/Solver-LF-0.0.0": {
          key: "services/computational/itis/Solver-LF",
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
        }
      };
      return builtInServices;
    },

    getFakeServices: function() {
      let services = {};
      services = Object.assign(services, this.getBuiltInServices());
      services = Object.assign(services, qxapp.dev.fake.Data.getNodeMap());
      return services;
    },

    getServices: function() {
      let req = new qxapp.io.request.ApiRequest("/services", "GET");
      req.addListener("success", e => {
        let requ = e.getTarget();
        const {
          data
        } = requ.getResponse();
        const listOfRepositories = data;
        let services = Object.assign({}, this.getBuiltInServices());
        for (const key in listOfRepositories) {
          const repoData = listOfRepositories[key];
          const nodeImageId = repoData.key + "-" + repoData.version;
          services[nodeImageId] = repoData;
        }
        if (this.__servicesCache === null) {
          this.__servicesCache = {};
        }
        this.__servicesCache = Object.assign(this.__servicesCache, services);
        this.fireDataEvent("servicesRegistered", services);
      }, this);

      req.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.log("getServices failed", error);
        let services = this.getFakeServices();
        if (this.__servicesCache === null) {
          this.__servicesCache = {};
        }
        this.__servicesCache = Object.assign(this.__servicesCache, services);
        this.fireDataEvent("servicesRegistered", services);
      }, this);
      req.send();
    },

    getS3SandboxFiles: function() {
      const slotName = "listObjects";
      let socket = qxapp.wrappers.WebSocket.getInstance();
      socket.removeSlot(slotName);
      socket.on(slotName, function(data) {
        console.log(slotName, data);
        this.fireDataEvent("S3PublicDocuments", data);
      }, this);
      socket.emit(slotName);

      if (!socket.getSocket().connected) {
        let data = qxapp.dev.fake.Data.getObjectList();
        console.log("Fake", slotName, data);
        this.fireDataEvent("S3PublicDocuments", data);
      }
    },

    getMyDocuments: function() {
      let reqLoc = new qxapp.io.request.ApiRequest("/storage/locations", "GET");

      reqLoc.addListener("success", eLoc => {
        const {
          dataLoc
        } = eLoc.getTarget().getResponse();
        const locations = dataLoc["locations"];
        for (let i=0; i<locations.length; i++) {
          const locationId = locations[i];
          const endPoint = "/storage/locations/" + locationId + "/files";
          let reqFiles = new qxapp.io.request.ApiRequest(endPoint, "GET");

          reqFiles.addListener("success", eFiles => {
            const {
              dataFiles
            } = eFiles.getTarget().getResponse();
            const files = dataFiles["files"];
            this.fireDataEvent("MyDocuments", files);
          }, this);

          reqFiles.addListener("fail", e => {
            const {
              error
            } = e.getTarget().getResponse();
            console.log("Failed getting Storage Locations", error);
          });
        }
      }, this);

      reqLoc.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.log("Failed getting Storage Locations", error);
      });
    }
  }
});
