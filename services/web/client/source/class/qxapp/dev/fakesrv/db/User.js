qx.Class.define("qxapp.dev.fakesrv.db.User", {
  type: "static",

  statics: {
    DUMMYNAMES: ["bizzy", "crespo", "guidon", "tobi", "maiz", "zastrow"],

    createMock: function(userId) {
      const uname = qxapp.dev.fakesrv.db.User.DUMMYNAMES[userId];
      let user = {
        id: userId,
        username: uname,
        fullname: qx.lang.String.capitalize(uname),
        email: uname + "@itis.ethz.ch",
        avatarUrl: qxapp.dev.Utils.getGravatar(uname + "@itis.ethz.ch", 200),
        projects: []
      };

      const pnames = qxapp.dev.fakesrv.db.Project.DUMMYNAMES;
      for (var i = 0; i < uname.length; i++) {
        const pid = i % pnames.length;
        user.projects.push(qxapp.dev.fakesrv.db.Project.createMock(pid));
      }
      return user;
    }
  }
});
