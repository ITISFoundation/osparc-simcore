qx.Class.define("qxapp.data.Store", {
  extend: qx.core.Object,

  type : "singleton",

  events: {
    "builtInServicesRegistered": "qx.event.type.Event",
    "servicesRegistered": "qx.event.type.Event",
    "interactiveServicesRegistered": "qx.event.type.Event"
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
    __servicesCacheBuiltIn: null,
    __servicesCacheComputational: null,
    __servicesCacheInteractive: null,

    getServices: function() {
      let services = {};
      services = Object.assign(services, this.getBuiltInServices());
      services = Object.assign(services, qxapp.dev.fake.Data.getNodeMap());
      return services;
    },

    getProjectList: function() {
      return qxapp.dev.fake.Data.getProjectList();
    },

    getNodeMetaData: function(nodeImageId) {
      let metaData = this.getServices()[nodeImageId];
      if (metaData === undefined) {
        metaData = this.getBuiltInServices()[nodeImageId];
      }
      return metaData;
    },

    getNodeMetaDataFromCache: function(nodeImageId) {
      let metadata = this.getNodeMetaData(nodeImageId);
      if (metadata) {
        return metadata;
      }
      let services = this.__servicesCacheBuiltIn.concat(this.__servicesCacheComputational);
      services = services.concat(this.__servicesCacheInteractive);
      for (let i=0; i<services.length; i++) {
        const service = services[i];
        const id = service.key + "-" + service.version;
        if (nodeImageId === id) {
          return service;
        }
      }
      return null;
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
        }
      };
      return builtInServices;
    },

    getBuiltInServicesAsync: function() {
      let builtInServices = [];
      let builtInServicesMap = this.getBuiltInServices();
      for (const mapKey of Object.keys(builtInServicesMap)) {
        builtInServices.push(builtInServicesMap[mapKey]);
      }

      console.log("builtInServicesRegistered", builtInServices);
      let services = [];
      for (const key of Object.keys(builtInServices)) {
        const repoData = builtInServices[key];
        let newMetaData = qxapp.data.Converters.registryToMetaData(repoData);
        services.push(newMetaData);
      }
      // this.fireDataEvent("builtInServicesRegistered", builtInServices);
      this.__servicesCacheBuiltIn = services;
      this.fireDataEvent("builtInServicesRegistered", services);
    },

    getComputationalServices: function() {
      let req = new qx.io.request.Xhr();
      req.set({
        url: "/get_computational_services",
        method: "GET"
      });
      req.addListener("success", function(e) {
        let requ = e.getTarget();
        const {
          data,
          status
        } = requ.getResponse();
        if (status >= 200 && status <= 299) {
          const listOfRepositories = data;
          console.log("listOfServices", listOfRepositories);
          let services = [];
          for (const key of Object.keys(listOfRepositories)) {
            const repoData = listOfRepositories[key];
            let newMetaData = qxapp.data.Converters.registryToMetaData(repoData);
            services.push(newMetaData);
          }
          this.__servicesCacheComputational = services;
          this.fireDataEvent("servicesRegistered", services);
        } else {
          // error
          console.error("Error retrieving services: ", data);
        }
      }, this);
      req.send();
    },

    getInteractiveServices: function() {
      let socket = qxapp.wrappers.WebSocket.getInstance();
      socket.removeSlot("getInteractiveServices");
      socket.on("getInteractiveServices", function(e) {
        const {
          data,
          status
        } = e;
        if (status >= 200 && status <= 299) {
          let listOfInteractiveServices = data;
          console.log("listOfInteractiveServices", listOfInteractiveServices);
          let services = [];
          for (const key of Object.keys(listOfInteractiveServices)) {
            const repoData = listOfInteractiveServices[key];
            let newMetaData = qxapp.data.Converters.registryToMetaData(repoData);
            services.push(newMetaData);
          }
          this.__servicesCacheInteractive = services;
          this.fireDataEvent("interactiveServicesRegistered", services);
        } else {
          // error
          console.error("Error retrieving services: ", data);
        }
      }, this);
      socket.emit("getInteractiveServices");
    }
  }
});
