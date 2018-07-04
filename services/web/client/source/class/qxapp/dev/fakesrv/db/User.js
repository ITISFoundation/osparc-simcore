qx.Class.define("qxapp.dev.fakesrv.db.User", {
  type: "static",

  statics: {
    DUMMYNAMES: ["bizzy", "crespo", "guidon", "tobi", "maiz", "zastrow"],

    /**
     * Creates a json object for a given user id
    */
    getObject: function(userId) {
      const uname = qxapp.dev.fakesrv.db.User.DUMMYNAMES[userId];
      let user = {
        id: userId,
        username: uname,
        fullname: qx.lang.String.capitalize(uname),
        email: qxapp.dev.fakesrv.db.User.getEmail(uname),
        avatarUrl: qxapp.utils.Avatar.getUrl(uname + "@itis.ethz.ch", 200),
        passwordHash: "z43", // This is
        projects: []
      };

      const pnames = qxapp.dev.fakesrv.db.Project.DUMMYNAMES;
      for (var i = 0; i < uname.length; i++) {
        const pid = i % pnames.length;
        user.projects.push(qxapp.dev.fakesrv.db.Project.createMock(pid));
      }
      return user;
    },

    getEmail: function(userId) {
      const userName = qxapp.dev.fakesrv.db.User.DUMMYNAMES[userId];
      return userName + "@itis.ethz.ch";
    }

  }
});
