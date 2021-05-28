qx.Class.define("osparc.dev.fake.srv.db.User", {
  type: "static",

  statics: {
    DUMMYNAMES: ["bizzy", "crespo", "anderegg", "guidon", "tobi", "maiz", "zastrow"],

    /**
     * Creates a json object for a given user id
    */
    getObject: function(userId) {
      const uname = osparc.dev.fake.srv.db.User.DUMMYNAMES[userId];
      const uemail = osparc.dev.fake.srv.db.User.getEmail(userId);
      let user = {
        id: userId,
        username: uname,
        fullname: qx.lang.String.capitalize(uname),
        email: uemail,
        avatarUrl: osparc.utils.Avatar.getUrl(uemail, 200),
        passwordHash: "z43", // This is supposed to be hashed
        projects: [] // Ids of projects associated to it
      };

      const pnames = osparc.dev.fake.srv.db.Project.DUMMYNAMES;
      for (let i = 0; i < uname.length; i++) {
        const pid = i % pnames.length;
        user.projects.push(osparc.dev.fake.srv.db.Project.getObject(pid));
      }
      return user;
    },

    getEmail: function(userId) {
      const userName = osparc.dev.fake.srv.db.User.DUMMYNAMES[userId];
      let tail = "@itis.ethz.ch";

      if (userName == "tobi") {
        tail = "@oetiker.ch";
      }
      return userName + tail;
    }

  }
});
