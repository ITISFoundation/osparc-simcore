/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/** Authentication data
 *
 *  - Keeps data and state of current authenticated (logged in) user
*/

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
      check: "qxapp.io.request.authentication.Token"
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
        qxapp.utils.Utils.cookie.setCookie("user", token);
        this.setAuth(new qxapp.io.request.authentication.Token(token));
      }
    },

    resetToken: function() {
      qxapp.utils.Utils.cookie.setCookie("user", "logout");
      this.resetAuth();
    },

    isLogout: function() {
      return qxapp.utils.Utils.cookie.getCookie("user") === "logout";
    },

    getUserName: function() {
      const email = qxapp.auth.Data.getInstance().getEmail();
      if (email) {
        return email.split("@")[0];
      }
      return "user";
    }
  }
});
