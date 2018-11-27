qx.Class.define("qxapp.data.Store", {
  extend: qx.core.Object,

  type : "singleton",

  events: {
    "servicesRegistered": "qx.event.type.Event",
    // "FakeFiles": "qx.event.type.Event",
    "MyDocuments": "qx.event.type.Event",
    "NodeFiles": "qx.event.type.Event",
    "PresginedLink": "qx.event.type.Event",
    "FileCopied": "qx.event.type.Event",
    "DeleteFile": "qx.event.type.Event"
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
    __servicesCached: null,

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

    arePortsCompatible: function(port1, port2) {
      const arePortsCompatible = this.__matchPortType(port1.type, port2.type);
      return arePortsCompatible;
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
        if (nodeImageId in this.__servicesCached) {
          return this.__servicesCached[nodeImageId];
        }
        metaData = this.getFakeServices()[nodeImageId];
        if (metaData === undefined) {
          metaData = this.getBuiltInServices()[nodeImageId];
        }
      }
      return metaData;
    },

    getItemList: function(nodeInstanceUUID, portKey) {
      return qxapp.dev.fake.Data.getItemList(nodeInstanceUUID, portKey);
    },

    getItem: function(nodeInstanceUUID, portKey, itemUuid) {
      return qxapp.dev.fake.Data.getItem(nodeInstanceUUID, portKey, itemUuid);
    },

    getBuiltInServices: function() {
      let builtInServices = {
        "simcore/services/dynamic/itis/file-picker-0.0.0": {
          key: "simcore/services/dynamic/itis/file-picker",
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
        "simcore/services/demodec/dynamic/itis/s4l/neuroman-0.0.0": {
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
        },
        "simcore/services/demodec/dynamic/itis/s4l/StimulationSelectivity-0.0.0": {
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
                leaf: "simcore/services/demodec/dynamic/itis/s4l/Modeler"
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
        "simcore/services/demodec/dynamic/itis/s4l/Modeler-0.0.0": {
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
        },
        "simcore/services/demodec/dynamic/itis/s4l/MaterialDB-0.0.0": {
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
        },
        "simcore/services/demodec/container/itis/s4l/Simulator/LF-0.0.0": {
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
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Setup-0.0.0": {
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
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Materials-0.0.0": {
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
            defaultMaterials: {
              displayOrder: 0,
              label: "Default Material Settings",
              description: "Default Material Settings",
              type: "node-output-tree-api-v0.0.1"
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
                branch: "simcore/services/demodec/dynamic/itis/s4l/MaterialDB",
                leaf: "simcore/services/demodec/dynamic/itis/s4l/Modeler"
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
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Boundary-0.0.0": {
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
            defaultBoundaries: {
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
                leaf: "simcore/services/demodec/dynamic/itis/s4l/Modeler"
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
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Sensors-0.0.0": {
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
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Grid-0.0.0": {
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
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Voxel-0.0.0": {
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
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/SolverSettings-0.0.0": {
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
        "simcore/services/demodec/computational/itis/Solver-LF-0.0.0": {
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

    getServices: function(reload) {
      if (reload || Object.keys(this.__servicesCached).length === 0) {
        let req = new qxapp.io.request.ApiRequest("/services", "GET");
        req.addListener("success", e => {
          let requ = e.getTarget();
          const {
            data
          } = requ.getResponse();
          const newServices = data;
          let services = Object.assign({}, this.getBuiltInServices());
          for (const key in newServices) {
            const service = newServices[key];
            const nodeImageId = service.key + "-" + service.version;
            services[nodeImageId] = service;
          }
          if (this.__servicesCached === null) {
            this.__servicesCached = {};
          }
          this.__servicesCached = Object.assign(this.__servicesCached, services);
          this.fireDataEvent("servicesRegistered", services);
        }, this);

        req.addListener("fail", e => {
          const {
            error
          } = e.getTarget().getResponse();
          console.log("getServices failed", error);
          let services = this.getFakeServices();
          if (this.__servicesCached === null) {
            this.__servicesCached = {};
          }
          this.__servicesCached = Object.assign(this.__servicesCached, services);
          this.fireDataEvent("servicesRegistered", services);
        }, this);
        req.send();
        return null;
      }
      return this.__servicesCached;
    },

    getFakeFiles: function() {
      let data = qxapp.dev.fake.Data.getObjectList();
      console.log("Fake Files", data);
      this.fireDataEvent("FakeFiles", data);
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
          this.fireDataEvent("NodeFiles", files);
        }
      }, this);

      reqFiles.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.log("Failed getting Node Files list", error);
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
          // Get list of file meta data
          const endPoint = "/storage/locations/" + locationId + "/files/metadata";
          let reqFiles = new qxapp.io.request.ApiRequest(endPoint, "GET");

          reqFiles.addListener("success", eFiles => {
            const files = eFiles.getTarget().getResponse()
              .data;
            console.log("My Files", files);
            if (files && files.length>0) {
              const data = {
                location: locationId,
                files: files
              };
              this.fireDataEvent("MyDocuments", data);
            }
          }, this);

          reqFiles.addListener("fail", e => {
            const {
              error
            } = e.getTarget().getResponse();
            console.log("Failed getting Files list", error);
          });

          reqFiles.send();
        }
      }, this);

      reqLoc.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.log("Failed getting Storage Locations", error);
      });

      reqLoc.send();
    },

    getPresginedLink: function(download = true, locationId, fileUuid) {
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
        const presginedLinkData = {
          presginedLink: data,
          locationId: locationId,
          fileUuid: fileUuid
        };
        console.log("PresginedLink", presginedLinkData);
        this.fireDataEvent("PresginedLink", presginedLinkData);
      }, this);

      req.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.log("Failed getting Presgined Link", error);
      });

      req.send();
    },

    copyFile: function(fromLoc, fileUuid, toLoc, pathId) {
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
        this.fireDataEvent("FileCopied", data);
      }, this);

      req.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.log(error);
        console.log("Failed copying file", fileUuid, "to", pathId);
      });

      req.send();
    },

    deleteFile: function(locationId, fileUuid) {
      // Deletes File
      let parameters = encodeURIComponent(fileUuid);
      const endPoint = "/storage/locations/" + locationId + "/files/" + parameters;
      let req = new qxapp.io.request.ApiRequest(endPoint, "DELETE");

      req.addListener("success", e => {
        const {
          data
        } = e.getTarget().getResponse();
        this.fireDataEvent("DeleteFile", data);
      }, this);

      req.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.log("Failed deleting file", error);
      });

      req.send();
    }
  }
});
