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
  extend: osparc.ui.list.ListItem,

  properties: {
    collabType: {
      check: [0, 1, 2], // 0:all, 1:org, 2:user
      event: "changeCollabType",
      nullable: true
    },

    accessRights: {
      check: "Object",
      apply: "__applyAccessRights",
      event: "changeAccessRights",
      nullable: true
    },

    showOptions: {
      check: "Boolean",
      apply: "__applyShowOptions",
      event: "changeShowOptions",
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
      const resource = this.getResourceType();
      if (["study", "template", "tutorial", "hypertool"].includes(resource)) {
        return osparc.data.Roles.STUDY[id];
      } else if (resource === "service") {
        return osparc.data.Roles.SERVICES[id];
      } else if (resource === "workspace") {
        return osparc.data.Roles.WORKSPACE[id];
      } else if (resource === "tag") {
        return osparc.data.Roles.STUDY[id];
      }
      return undefined;
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "options": {
          const iconSize = 25;
          control = new qx.ui.form.MenuButton().set({
            maxWidth: iconSize,
            maxHeight: iconSize,
            alignX: "center",
            alignY: "middle",
            icon: "@FontAwesome5Solid/ellipsis-v/"+(iconSize-11),
            focusable: false
          });
          this._add(control, {
            row: 0,
            column: 3,
            rowSpan: 2
          });
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    // overridden
    _applyTitle: function(value) {
      if (value === null) {
        return;
      }
      const groupsStore = osparc.store.Groups.getInstance();
      const everyoneGroupIds = [
        groupsStore.getEveryoneProductGroup().getGroupId(),
        groupsStore.getEveryoneGroup().getGroupId(),
      ];
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
          case 0:
            value = "@FontAwesome5Solid/globe/28";
            break;
          case 1:
            value = "@FontAwesome5Solid/users/28";
            break;
          case 2:
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
        this.addState("selected");
      }
    },

    __applyAccessRights: function(value) {
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
          const resource = this.getResourceType();
          const promoteButton = new qx.ui.menu.Button(this.tr(`Promote to ${this.__getRoleInfo("delete").label}`));
          promoteButton.setVisibility(resource === "service" ? "excluded" : "visible");
          promoteButton.addListener("execute", () => {
            this.fireDataEvent("promoteToOwner", {
              gid: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(promoteButton);
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

    __applyShowOptions: function(value) {
      const optionsMenu = this.getChildControl("options");
      optionsMenu.setVisibility(value ? "visible" : "excluded");
    }
  }
});
