qx.Class.define("qxapp.data.Store", {
  extend: qx.core.Object,

  type : "singleton",

  events: {
    "servicesRegistered": "qx.event.type.Event",
    "interactiveServicesRegistered": "qx.event.type.Event"
  },

  members: {
    getBuiltInServices: function() {
      let builtInServices = [{
        "key": "FileManager",
        "name": "File Manager",
        "tag": "0.0.1",
        "description": "File Manager",
        "authors": [{
          "name": "Odei Maiz",
          "email": "maiz@itis.ethz.ch",
          "affiliation": "ITIS Foundation"
        }],
        "contact": "maiz@itis.ethz.ch",
        "inputs": [],
        "outputs": [{
          "key": "out_1",
          "label": "File-url",
          "description": "File-url",
          "type": "file-url",
          "defaultValue": null
        }, {
          "key": "out_2",
          "label": "Folder-url",
          "description": "Folder-url",
          "type": "folder-url",
          "defaultValue": null
        }],
        "settings": []
      }];
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
            let newMetadata = qxapp.data.Converters.registryToMetadata(repo[i]);
            services.push(newMetadata);
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
            let newMetadata = qxapp.data.Converters.registryToMetadata(repoData);
            services.push(newMetadata);
          }
        }
        this.fireDataEvent("interactiveServicesRegistered", services);
      }, this);
      socket.emit("getInteractiveServices");
    }
  }
});
