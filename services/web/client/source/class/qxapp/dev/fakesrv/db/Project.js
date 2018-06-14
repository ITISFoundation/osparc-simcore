qx.Class.define("qxapp.dev.fakesrv.db.Project", {
  type: "static",

  statics: {
    DUMMYNAMES: ["My EM-Simulation", "FDTD-Simulation", "Some Neuro-Simulatoin", "Clancy Model", "DemoPrj", "LF Simulation"],

    createMock: function(projectId) {
      const name = qxapp.dev.fakesrv.db.Project.DUMMYNAMES[projectId];
      let project = {
        id: projectId,
        name: name,
        description: "Short description of project " + name,
        thumbnail: "https://imgplaceholder.com/171x96/cccccc/757575/ion-plus-round",
        createdDate: Date.now(),
        modifiedDate: Date.now()
      };
      return project;
    }
  }
});
