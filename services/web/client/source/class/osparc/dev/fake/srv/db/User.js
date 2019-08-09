qx.Class.define("qxapp.dev.fake.srv.db.User", {
  type: "static",

  statics: {
    DUMMYNAMES: ["bizzy", "crespo", "anderegg", "guidon", "tobi", "maiz", "zastrow"],

    /**
     * Creates a json object for a given user id
    */
    getObject: function(userId) {
      const uname = qxapp.dev.fake.srv.db.User.DUMMYNAMES[userId];
      const uemail = qxapp.dev.fake.srv.db.User.getEmail(userId);
      let user = {
        id: userId,
        username: uname,
        fullname: qx.lang.String.capitalize(uname),
        email: uemail,
        avatarUrl: qxapp.utils.Avatar.getUrl(uemail, 200),
        passwordHash: "z43", // This is supposed to be hashed
        projects: [] // Ids of projects associated to it
      };

      const pnames = qxapp.dev.fake.srv.db.Project.DUMMYNAMES;
      for (let i = 0; i < uname.length; i++) {
        const pid = i % pnames.length;
        user.projects.push(qxapp.dev.fake.srv.db.Project.getObject(pid));
      }
      return user;
    },

    getEmail: function(userId) {
      const userName = qxapp.dev.fake.srv.db.User.DUMMYNAMES[userId];
      let tail = "@itis.ethz.ch";

      if (userName == "tobi") {
        tail = "@oetiker.ch";
      }
      return userName + tail;
    }

  }
});
