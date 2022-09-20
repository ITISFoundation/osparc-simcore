qx.Class.define("osparc.dev.fake.srv.db.Project", {
  type: "static",

  statics: {
    DUMMYNAMES: ["My EM-Simulation", "FDTD-Simulation", "Some Neuro-Simulatoin", "Clancy Model", "DemoPrj", "LF Simulation"],

    /**
     * Creates a json object for a given study id
    */
    getObject: function(studyId) {
      const name = osparc.dev.fake.srv.db.Project.DUMMYNAMES[studyId];
      let study = {
        id: studyId,
        name: name,
        description: "Short description of study " + name,
        thumbnail: "https://imgplaceholder.com/171x96/cccccc/757575/ion-plus-round",
        createdDate: new Date(1990 + name.length, 11, 25),
        modifiedDate: new Date(1990 + name.length, 12, 25)
      };
      return study;
    }
  }
});
