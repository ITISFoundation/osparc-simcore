/** Authentication data
 *
 *  - Keeps data and state of current authenticated (logged in) user
*/
/* eslint no-warning-comments: "off" */
qx.Class.define("qxapp.auth.Data", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    /**
     *  Basic authentification with a token
    */
    auth: {
      init: null,
      nullable: true,
      check: "qx.io.request.authentication.Basic"
    },

    /**
     *  Email of logged in user, otherwise null
    */
    email: {
      init: null,
      nullable: true,
      check: "String"
    }
  },

  members: {

    setToken: function(token) {
      if (token) {
        this.setAuth(new qx.io.request.authentication.Basic(token, null));
      }
    },

    resetToken: function() {
      this.resetAuth();
    },

    getUserName: function() {
      const email = qxapp.auth.Data.getInstance().getEmail();
      if (email) {
        return email.split("@")[0];
      }
      return null;
    }
  }
});
