qx.Class.define("qxapp.data.Store", {
  extend: qx.core.Object,

  type : "singleton",

  events: {
    "servicesRegistered": "qx.event.type.Event"
  },

  members: {
    getServices: function() {
      let req = new qx.io.request.Xhr();
      req.set({
        url: "/repositories",
        method: "GET"
      });
      req.addListener("success", function(e) {
        let requ = e.getTarget();
        const listOfRepositories = JSON.parse(requ.getResponse());
        let services = [];
        for (const key of Object.keys(listOfRepositories)) {
          const repo = listOfRepositories[key];
          const nTags = repo.length;
          for (let i=0; i<nTags; i++) {
            console.log(i, repo[i]);
            let newMetadata = qxapp.data.Converters.registryToMetadata(repo[i]);
            services.push(newMetadata);
          }
        }
        this.fireDataEvent("servicesRegistered", services);
      }, this);
      req.send();
    }
  }
});
