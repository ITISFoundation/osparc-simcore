/* ************************************************************************

   osparc - the simcore frontend

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

qx.Class.define("osparc.auth.Data", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    /**
     *  User Id
     */
    userId: {
      init: null,
      nullable: false,
      check: "Number"
    },

    /**
     *  Group ID
     */
    groupId: {
      init: null,
      nullable: false,
      check: "Number"
    },

    /**
     *  org IDs
     */
    orgIds: {
      init: [],
      nullable: false,
      check: "Array"
    },

    /**
     *  Basic authentification with a token
    */
    auth: {
      init: null,
      nullable: true,
      check: "osparc.io.request.authentication.Token"
    },

    /**
     *  Email of logged in user, otherwise null
    */
    email: {
      init: null,
      nullable: true,
      check: "String"
    },

    firstName: {
      init: "",
      nullable: true,
      check: "String",
      event: "changeFirstName"
    },

    lastName: {
      init: "",
      nullable: true,
      check: "String"
    },

    role: {
      check: ["anonymous", "guest", "user", "tester", "admin"],
      init: null,
      nullable: false,
      event: "changeRole"
    },

    expirationDate: {
      init: null,
      nullable: true,
      check: "Date",
      event: "changeExpirationDate"
    }
  },

  members: {

    setToken: function(token) {
      if (token) {
        osparc.utils.Utils.cookie.setCookie("user", token);
        this.setAuth(new osparc.io.request.authentication.Token(token));
      }
    },

    resetToken: function() {
      osparc.utils.Utils.cookie.setCookie("user", "logout");
      this.resetAuth();
    },

    isLogout: function() {
      return osparc.utils.Utils.cookie.getCookie("user") === "logout";
    },

    getUserName: function() {
      const firstName = this.getFirstName();
      if (firstName) {
        return firstName;
      }
      const email = this.getEmail();
      if (email) {
        return osparc.utils.Utils.getNameFromEmail(email);
      }
      return "user";
    }
  }
});
