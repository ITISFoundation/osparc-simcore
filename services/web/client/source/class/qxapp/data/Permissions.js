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

/**
 * Singleton class for building Permission table and check doable operations.
 *
 * It implements HRBAC (Hierarchical Role Based Access Control) permission model.
 *
 * It is able to:
 * - add Actions to build a table of permissions
 * - load User's Role from the backend
 * - check whether a role can do a specific actions
 *
 * *Example*
 *
 * Here is a little example of how to use the class.
 *
 * <pre class='javascript'>
 *   qxapp.data.Permissions.getInstance().canDo("test")
 * </pre>
 */

qx.Class.define("qxapp.data.Permissions", {
  extend: qx.core.Object,

  type : "singleton",

  construct() {
    this.addAction("tester", "show_all_services");
    this.addAction("user", "go_to_dashboard");
    this.addAction("user", "write_node");
    this.addAction("user", "write_link");
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

    canDo: function(action, showMsg) {
      let canDo = false;
      if (this.__userRole) {
        canDo = this.__canRoleDo(this.__userRole, action);
      }
      if (showMsg && !canDo) {
        qxapp.component.widget.FlashMessenger.getInstance().logAs("Operation not permitted", "ERROR");
      }
      return canDo;
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
