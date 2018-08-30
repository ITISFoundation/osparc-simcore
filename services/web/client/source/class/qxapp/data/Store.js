qx.Class.define("qxapp.data.Store", {
  extend: qx.core.Object,

  type : "singleton",

  events: {
    "servicesRegistered": "qx.event.type.Event",
    "interactiveServicesRegistered": "qx.event.type.Event"
  },

  members: {
    getServices: function() {
      let services = {};
      services = Object.assign(services, this.getBuiltInServices());
      services = Object.assign(services, qxapp.dev.fake.Data.getNodeMap());
      return services;
    },

    getProjectList: function() {
      return qxapp.dev.fake.Data.getProjectList();
    },

    getProjectData: function(projectUuid) {
      return qxapp.dev.fake.Data.getProjectData(projectUuid);
    },

    getNodeMetaData: function(nodeImageId) {
      let metaData = this.getServices()[nodeImageId];
      if (metaData === undefined) {
        metaData = this.getBuiltInServices()[nodeImageId];
      }
      return metaData;
    },

    getBuiltInServices: function() {
      let builtInServices = {
        "service/dynamic/itis/FileManager-0.0.0": {
          key: "service/dynamic/itis/FileManager",
          version: "0.0.0",
          type: "dynamic",
          name: "File Manager",
          description: "File Manager",
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
            },
            outDir: {
              displayOrder: 1,
              label: "Folder",
              description: "Chosen Folder",
              type: "data:*/*"
            }
          }
        },
        "service/container/itis/Simulator-LF-0.0.0": {
          key: "service/container/itis/Simulator-LF",
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
              label: "modeler",
              description: "Live link to Modeler",
              type: "data:*/*"
            },
            materialDB: {
              displayOrder: 1,
              label: "materialDB",
              description: "Live link to Material DB",
              type: "data:*/*"
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
          innerServices: [
            {
              key: "service/computational/itis/Simulator-LF/Setup",
              version: "0.0.0",
              type: "computational",
              name: "Setup Settings",
              description: "LF Simulator Setup Settings",
              inputs: {
                setupSetting: {
                  displayOrder: 0,
                  label: "SetupSetting",
                  description: "Setup Setting",
                  type: "number",
                  defaultValue: 1
                }
              }
            }, {
              key: "service/dynamic/itis/Simulator-LF/Material",
              version: "0.0.0",
              type: "dynamic",
              name: "Material Settings",
              description: "LF Simulator Material Settings",
              inputs: {
                modeler: {
                  displayOrder: 0,
                  label: "Modeler",
                  description: "Live Link to Modeler",
                  type: "object",
                  defaultValue: {
                    innerInput: "modeler"
                  }
                },
                materialDB: {
                  displayOrder: 1,
                  label: "MaterialDB",
                  description: "Live Link to Material DB",
                  type: "object",
                  defaultValue: {
                    innerInput: "materialDB"
                  }
                },
                materialSetting: {
                  displayOrder: 2,
                  label: "MaterialSetting",
                  description: "Material Setting",
                  type: "number",
                  defaultValue: 2
                }
              }
            }, {
              key: "service/dynamic/itis/Simulator-LF/Boundary",
              version: "0.0.0",
              type: "dynamic",
              name: "Boundary Conditions",
              description: "LF Simulator Boundary Conditions",
              inputs: {
                modeler: {
                  displayOrder: 0,
                  label: "modeler",
                  description: "Live Link to Modeler",
                  type: "object",
                  defaultValue: {
                    innerInput: "modeler"
                  }
                },
                boundarySetting: {
                  displayOrder: 1,
                  label: "BoundaryConditions",
                  description: "Boundary Conditions",
                  type: "number",
                  defaultValue: 3
                }
              }
            }
          ]
        },
        "service/computational/itis/Solver-LF-0.0.0": {
          key: "service/computational/itis/Solver-LF",
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

    getComputationalServices: function() {
      let req = new qx.io.request.Xhr();
      req.set({
        url: "/get_computational_services",
        method: "GET"
      });
      req.addListener("success", function(e) {
        let requ = e.getTarget();
        const listOfRepositories = JSON.parse(requ.getResponse());
        console.log("listOfServices", listOfRepositories);
        let services = [];
        for (const key of Object.keys(listOfRepositories)) {
          const repo = listOfRepositories[key];
          const nTags = repo.length;
          for (let i=0; i<nTags; i++) {
            let newMetaData = qxapp.data.Converters.registryToMetaData(repo[i]);
            services.push(newMetaData);
          }
        }
        this.fireDataEvent("servicesRegistered", services);
      }, this);
      req.send();
    },

    getInteractiveServices: function() {
      let socket = qxapp.wrappers.WebSocket.getInstance();
      socket.removeSlot("getInteractiveServices");
      socket.on("getInteractiveServices", function(e) {
        let listOfIntercativeServices = e;
        console.log("listOfIntercativeServices", listOfIntercativeServices);
        let services = [];
        for (const key of Object.keys(listOfIntercativeServices)) {
          const repo = listOfIntercativeServices[key];
          if (repo["details"].length>0 && repo["details"][0].length>0) {
            const repoData = repo["details"][0][0];
            let newMetaData = qxapp.data.Converters.registryToMetaData(repoData);
            services.push(newMetaData);
          }
        }
        this.fireDataEvent("interactiveServicesRegistered", services);
      }, this);
      socket.emit("getInteractiveServices");
    }
  }
});
