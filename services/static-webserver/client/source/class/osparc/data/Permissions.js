/* ************************************************************************

   osparc - the simcore frontend

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
 *   osparc.data.Permissions.getInstance().canDo("study.start", true)
 * </pre>
 */

qx.Class.define("osparc.data.Permissions", {
  extend: qx.core.Object,
  type: "singleton",

  construct() {
    const initPermissions = this.self().getInitPermissions();
    for (const role in initPermissions) {
      if (Object.prototype.hasOwnProperty.call(initPermissions, role)) {
        initPermissions[role].forEach(action => {
          this.addAction(role, action);
        }, this);
      }
    }
  },

  statics: {
    ACTIONS: {},

    ROLES_APP: {
      anonymous: {
        can: [],
        inherits: []
      },
      guest: {
        can: [],
        inherits: ["anonymous"]
      },
      user: {
        can: [],
        inherits: ["guest"]
      },
      tester: {
        can: [],
        inherits: ["user"]
      },
      "product_owner": {
        can: [],
        inherits: ["tester"]
      },
      admin: {
        can: [],
        inherits: ["product_owner"]
      }
    },

    getInitPermissions: function() {
      const initPermissions = {
        "anonymous": [],
        "guest": [
          "studies.templates.read",
          "study.node.data.pull",
          "study.start",
          "study.stop",
          "study.update"
        ],
        "user": [
          "dashboard.read",
          "dashboard.templates.read",
          "dashboard.services.read",
          "dashboard.data.read",
          "studies.user.read",
          "studies.user.create",
          "studies.template.create",
          "studies.template.update",
          "studies.template.delete",
          "storage.datcore.read",
          "user.user.update",
          "user.apikey.create",
          "user.apikey.delete",
          "user.token.create",
          "user.token.delete",
          "user.tag",
          "user.organizations.create",
          "study.node.create",
          "study.node.delete",
          "study.node.update",
          "study.node.rename",
          "study.node.start",
          "study.node.data.push",
          "study.node.data.delete",
          "study.node.export",
          "study.node.bootOptions.read",
          "study.edge.create",
          "study.edge.delete",
          "study.classifier",
          "study.tag",
          "study.slides.edit",
          "study.slides.stop",
          "usage.all.read"
        ],
        "tester": [
          "studies.template.create.all",
          "studies.template.create.productAll",
          "services.all.read",
          "services.all.reupdate",
          "services.filePicker.read.all",
          "user.clusters.create",
          "user.wallets.create",
          "study.everyone.share",
          "study.snapshot.read",
          "study.snapshot.create",
          "study.nodestree.uuid.read",
          "study.filestree.uuid.read",
          "study.logger.debug.read",
        ],
        "product_owner": [
          "user.invitation.generate",
          "user.users.search",
          "user.users.pre-register"
        ],
        "admin": []
      };
      let fromUserToTester = [];
      if (osparc.product.Utils.isProduct("tis") || osparc.product.Utils.isProduct("tiplite")) {
        // "templates" and "services" tabs only for testers
        // start/stop/edit app mode only for testers
        fromUserToTester = [
          "dashboard.templates.read",
          "dashboard.services.read",
          "study.node.bootOptions.read",
          "study.slides.edit",
          "study.slides.stop"
        ];
      } else if (osparc.product.Utils.isProduct("s4llite")) {
        // "services" tabs only for testers
        fromUserToTester = [
          "dashboard.services.read"
        ];
      }
      fromUserToTester.forEach(onlyTester => {
        const idx = initPermissions.user.indexOf(onlyTester);
        if (idx > -1) {
          initPermissions.user.splice(idx, 1);
        }
        initPermissions.tester.push(onlyTester);
      });
      return initPermissions;
    }
  },

  properties: {
    role: {
      check: ["anonymous", "guest", "user", "tester", "product_owner", "admin"],
      init: null,
      nullable: false,
      event: "changeRole"
    }
  },

  members: {
    arePermissionsReady() {
      return this.getRole() !== null;
    },

    getChildrenRoles(role) {
      role = role.toLowerCase();
      const childrenRoles = [];
      if (!this.self().ROLES_APP[role]) {
        return childrenRoles;
      }
      if (!childrenRoles.includes(role)) {
        childrenRoles.unshift(role);
      }
      const children = this.self().ROLES_APP[role].inherits;
      for (let i=0; i<children.length; i++) {
        const child = children[i];
        if (!childrenRoles.includes(child)) {
          childrenRoles.unshift(child);
          const moreChildren = this.getChildrenRoles(child);
          for (let j=moreChildren.length-1; j>=0; j--) {
            if (!childrenRoles.includes(moreChildren[j])) {
              childrenRoles.unshift(moreChildren[j]);
            }
          }
        }
      }
      return childrenRoles;
    },

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
      if (!this.self().ROLES_APP[role]) {
        return;
      }

      this.self().ACTIONS[action] = this.__nextAction();
      this.self().ROLES_APP[role].can.push(action);
    },

    // https://blog.nodeswat.com/implement-access-control-in-node-js-8567e7b484d1#2405
    canRoleDo: function(role, action) {
      role = role.toLowerCase();
      // Check if role exists
      const roles = this.self().ROLES_APP;
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
      return roleObj.inherits.some(childRole => this.canRoleDo(childRole, action));
    },

    canDo: function(action, showMsg) {
      let canDo = false;
      if (this.getRole()) {
        canDo = this.canRoleDo(this.getRole(), action);
      }
      if (showMsg && !canDo) {
        let msg = "Operation not permitted";
        if (["anonymous", "guest"].includes(this.getRole())) {
          msg = "Please register to use this functionality";
        }
        osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
      }
      return canDo;
    },

    checkCanDo: function(action) {
      return new Promise((resolve, reject) => {
        osparc.data.Resources.get("permissions")
          .then(permissions => {
            const found = permissions.find(permission => permission["name"] === action);
            if (found) {
              resolve(found["allowed"]);
            } else {
              resolve(false);
            }
          })
          .catch(err => reject(err));
      });
    },

    isTester: function() {
      return ["admin", "product_owner", "tester"].includes(this.getRole());
    },

    isProductOwner: function() {
      return this.getRole() === "product_owner";
    },

    isAdmin: function() {
      return this.getRole() === "admin";
    },
  }
});
