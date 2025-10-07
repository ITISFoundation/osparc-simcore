/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.list.CollaboratorListItem", {
  extend: osparc.ui.list.ListItemWithMenu,

  properties: {
    collabType: {
      check: [
        "everyone",     // osparc.store.Groups.COLLAB_TYPE.EVERYONE
        "support",      // osparc.store.Groups.COLLAB_TYPE.SUPPORT
        "organization", // osparc.store.Groups.COLLAB_TYPE.ORGANIZATION
        "user",         // osparc.store.Groups.COLLAB_TYPE.USER
      ],
      event: "changeCollabType",
      nullable: true
    },

    resourceType : {
      check: "String",
      event: "changeResourceType",
      nullable: false
    }
  },

  events: {
    "promoteToEditor": "qx.event.type.Data",
    "promoteToOwner": "qx.event.type.Data",
    "demoteToUser": "qx.event.type.Data",
    "demoteToEditor": "qx.event.type.Data",
    "removeMember": "qx.event.type.Data"
  },

  statics: {
    canDelete: function(accessRights) {
      const canDelete = accessRights.getDelete ? accessRights.getDelete() : false;
      return canDelete;
    },

    canWrite: function(accessRights) {
      let canWrite = accessRights.getWrite ? accessRights.getWrite() : false;
      canWrite = canWrite || (accessRights.getWriteAccess ? accessRights.getWriteAccess() : false);
      return canWrite;
    },

    canRead: function(accessRights) {
      let canRead = accessRights.getRead ? accessRights.getRead() : false;
      canRead = canRead || (accessRights.getExecuteAccess ? accessRights.getExecuteAccess() : false);
      return canRead;
    }
  },

  members: {
    __getRoleInfo: function(id) {
      let roleInfo = undefined;
      const resource = this.getResourceType();
      switch (resource) {
        case "study":
        case "template":
        case "tutorial":
        case "hypertool":
        case "tag":
          roleInfo = osparc.data.Roles.STUDY[id];
          break;
        case "function":
          roleInfo = osparc.data.Roles.FUNCTION[id];
          break;
        case "service":
          roleInfo = osparc.data.Roles.SERVICES[id];
          break;
        case "workspace":
          roleInfo = osparc.data.Roles.WORKSPACE[id];
          break;
      }
      return roleInfo;
    },

    // overridden
    _applyTitle: function(value) {
      if (value === null) {
        return;
      }
      const groupsStore = osparc.store.Groups.getInstance();
      const everyoneGroupIds = groupsStore.getEveryoneGroupIds();
      const label = this.getChildControl("title");
      if (everyoneGroupIds.includes(this.getModel())) {
        label.setValue(this.tr("Public"));
      } else {
        label.setValue(value);
      }
    },

    // overridden
    _applyThumbnail: function(value) {
      if (value === null) {
        const collabType = this.getCollabType();
        switch (collabType) {
          case osparc.store.Groups.COLLAB_TYPE.EVERYONE:
            value = "@FontAwesome5Solid/globe/28";
            break;
          case osparc.store.Groups.COLLAB_TYPE.ORGANIZATION:
            value = "@FontAwesome5Solid/users/28";
            break;
          case osparc.store.Groups.COLLAB_TYPE.USER:
            value = "@FontAwesome5Solid/user/28";
            break;
        }
      }
      this.base(arguments, value);
    },

    // overridden
    _applySubtitleMD: function(value) {
      this.base(arguments, value);

      // highlight me
      const email = osparc.auth.Data.getInstance().getEmail();
      if (value && value.includes(email)) {
        this.setBackgroundColor("background-selected");
      } else {
        this.setBackgroundColor("background-main-2");
      }
    },

    // overridden
    _applyAccessRights: function(value) {
      if (value === null) {
        return;
      }

      this.__setRole();

      const menu = this.__getOptionsMenu();
      const optionsMenu = this.getChildControl("options");
      optionsMenu.setMenu(menu);
    },

    __setRole: function() {
      const accessRights = this.getAccessRights();
      const role = this.getChildControl("role");
      if (this.self().canDelete(accessRights)) {
        role.setValue(this.__getRoleInfo("delete").label);
      } else if (this.self().canWrite(accessRights)) {
        role.setValue(this.__getRoleInfo("write").label);
      } else {
        role.setValue(this.__getRoleInfo("read").label);
      }
    },

    __getOptionsMenu: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const collabAccessRights = this.getAccessRights();
      let collabCurrentRole = this.__getRoleInfo("read");
      if (this.self().canDelete(collabAccessRights)) {
        collabCurrentRole = this.__getRoleInfo("delete");
      } else if (this.self().canWrite(collabAccessRights)) {
        collabCurrentRole = this.__getRoleInfo("write");
      }

      // promote/demote actions
      switch (collabCurrentRole.id) {
        case "read": {
          const promoteButton = new qx.ui.menu.Button(this.tr(`Promote to ${this.__getRoleInfo("write").label}`));
          promoteButton.addListener("execute", () => {
            this.fireDataEvent("promoteToEditor", {
              gid: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(promoteButton);
          break;
        }
        case "write": {
          // there might not be delete role
          const deleteRole = this.__getRoleInfo("delete");
          if (deleteRole) {
            const promoteButton = new qx.ui.menu.Button(this.tr(`Promote to ${this.__getRoleInfo("delete").label}`));
            promoteButton.addListener("execute", () => {
              this.fireDataEvent("promoteToOwner", {
                gid: this.getKey(),
                name: this.getTitle()
              });
            });
            menu.add(promoteButton);
          }
          const demoteButton = new qx.ui.menu.Button(this.tr(`Demote to ${this.__getRoleInfo("read").label}`));
          demoteButton.addListener("execute", () => {
            this.fireDataEvent("demoteToUser", {
              gid: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(demoteButton);
          break;
        }
        case "delete": {
          const demoteButton = new qx.ui.menu.Button(this.tr(`Demote to ${this.__getRoleInfo("write").label}`));
          demoteButton.addListener("execute", () => {
            this.fireDataEvent("demoteToEditor", {
              gid: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(demoteButton);
          break;
        }
      }

      if (menu.getChildren().length) {
        menu.addSeparator();
      }

      const removeButton = new qx.ui.menu.Button(this.tr(`Remove ${collabCurrentRole.label}`)).set({
        textColor: "danger-red"
      });
      removeButton.addListener("execute", () => {
        this.fireDataEvent("removeMember", {
          gid: this.getKey(),
          name: this.getTitle()
        });
      });
      menu.add(removeButton);

      return menu;
    },
  }
});
