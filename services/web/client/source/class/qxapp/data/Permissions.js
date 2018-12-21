/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("qxapp.data.Permissions", {
  extend: qx.core.Object,

  type : "singleton",

  construct() {
    this.addAction("tester", "test");
  },

  events: {
    "userProfileRecieved": "qx.event.type.Event"
  },

  statics: {
    ACTIONS: {},

    ROLES: {
      anonymous: {
        can: []
      },
      user: {
        can: [],
        inherits: ["anonymous"]
      },
      tester: {
        can: [],
        inherits: ["user"]
      },
      moderator: {
        can: [],
        inherits: ["tester"]
      },
      admin: {
        can: [],
        inherits: ["moderator"]
      }
    }
  },

  members: {
    __userRole: null,

    __nextAction: function() {
      let highestAction = 0.5;
      for (const key in this.self().ACTIONS) {
        if (highestAction < this.self().ACTIONS[key]) {
          highestAction = this.self().ACTIONS[key];
        }
      }
      return 2*highestAction;
    },

    addAction: function(role, action) {
      if (!this.self().ROLES[role]) {
        return;
      }

      this.self().ACTIONS[action] = this.__nextAction();
      this.self().ROLES[role].can.push(action);
    },

    // https://blog.nodeswat.com/implement-access-control-in-node-js-8567e7b484d1#2405
    __canRoleDo: function(role, action) {
      role = role.toLowerCase();
      // Check if role exists
      const roles = this.self().ROLES;
      if (!roles[role]) {
        return false;
      }
      let roleObj = roles[role];
      // Check if this role has access
      if (roleObj.can.indexOf(action) !== -1) {
        return true;
      }
      // Check if there are any parents
      if (!roleObj.inherits || roleObj.inherits.length < 1) {
        return false;
      }
      // Check child roles until one returns true or all return false
      return roleObj.inherits.some(childRole => this.__canRoleDo(childRole, action));
    },

    canDo: function(action) {
      if (this.__userRole) {
        return this.__canRoleDo(this.__userRole, action);
      }
      return false;
    },

    loadUserRoleFromBackend: function() {
      let userResources = qxapp.io.rest.ResourceFactory.getInstance().createUserResources();

      let profile = userResources.profile;
      profile.addListenerOnce("getSuccess", e => {
        let profileData = e.getRequest().getResponse().data;
        this.__userRole = profileData.role;
        this.fireDataEvent("userProfileRecieved", true);
      }, this);
      profile.addListenerOnce("getError", e => {
        console.error(e);
      });
      profile.get();
    }
  }
});
