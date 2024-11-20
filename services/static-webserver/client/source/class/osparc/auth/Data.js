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
     *  Basic authentification with a token
    */
    auth: {
      init: null,
      nullable: true,
      check: "osparc.io.request.authentication.Token",
      apply: "__applyAuth"
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
      check: "String",
      event: "changeLastName"
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

    expirationDate: {
      init: null,
      nullable: true,
      check: "Date",
      event: "changeExpirationDate"
    },

    loggedIn: {
      check: "Boolean",
      nullable: false,
      init: false,
      event: "changeLoggedIn",
    }
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
    },

    getFriendlyRole: function() {
      const role = this.getRole();
      let friendlyRole = role.replace(/_/g, " ");
      friendlyRole = osparc.utils.Utils.firstsUp(friendlyRole);
      return friendlyRole;
    }
  }
});
