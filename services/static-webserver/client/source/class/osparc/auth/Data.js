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
     *  Basic authentification with a token
    */
    auth: {
      init: null,
      nullable: true,
      check: "osparc.io.request.authentication.Token",
      apply: "__applyAuth"
    },

    role: {
      check: ["anonymous", "guest", "user", "tester", "product_owner", "admin"],
      init: null,
      nullable: false,
      event: "changeRole",
      apply: "__applyRole"
    },

    guest: {
      check: "Boolean",
      init: true,
      nullable: false,
      event: "changeGuest"
    },

    loggedIn: {
      check: "Boolean",
      nullable: false,
      init: false,
      event: "changeLoggedIn",
    },

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

    username: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeUsername",
    },

    email: {
      init: null,
      nullable: true, // email of logged in user, otherwise null
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
      check: "String",
      event: "changeLastName"
    },

    expirationDate: {
      init: null,
      nullable: true,
      check: "Date",
      event: "changeExpirationDate"
    },
  },

  members: {
    __applyAuth: function(auth) {
      this.setLoggedIn(auth !== null && auth instanceof osparc.io.request.authentication.Token);
    },

    __applyRole: function(role) {
      if (role && ["user", "tester", "product_owner", "admin"].includes(role)) {
        this.setGuest(false);
      } else {
        this.setGuest(true);
      }
    },

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

    getFriendlyUsername: function() {
      const firstName = this.getFirstName();
      if (firstName) {
        return firstName;
      }
      return this.getUsername();
    },

    getFullName: function() {
      let name = "";
      if (this.getFirstName()) {
        name += this.getFirstName();
      }
      if (this.getLastName()) {
        name += " " + this.getLastName();
      }
      return name;
    },

    getFriendlyRole: function() {
      const role = this.getRole();
      let friendlyRole = role.replace(/_/g, " ");
      friendlyRole = osparc.utils.Utils.firstsUp(friendlyRole);
      return friendlyRole;
    }
  }
});
