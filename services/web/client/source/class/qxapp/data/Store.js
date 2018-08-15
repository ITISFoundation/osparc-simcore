qx.Class.define("qxapp.data.Store", {
  extend: qx.core.Object,

  type : "singleton",

  events: {
    "servicesRegistered": "qx.event.type.Event",
    "interactiveServicesRegistered": "qx.event.type.Event"
  },

  members: {
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
              type: "string"
            },
            outDir: {
              displayOrder: 1,
              label: "Folder",
              description: "Chosen Folder",
              type: "string"
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
