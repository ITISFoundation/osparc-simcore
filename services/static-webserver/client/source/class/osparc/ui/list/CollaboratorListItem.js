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
    __getRoleInfo: function(i) {
      const resource = this.getResourceType();
      if (resource === "study" || resource === "template") {
        return osparc.data.Roles.STUDY[i];
      } else if (resource === "service") {
        return osparc.data.Roles.SERVICES[i];
      } else if (resource === "workspace") {
        return osparc.data.Roles.WORKSPACE[i];
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
      if (email === value) {
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
        role.setValue(this.__getRoleInfo(3).label);
      } else if (this.self().canWrite(accessRights)) {
        role.setValue(this.__getRoleInfo(2).label);
      } else {
        role.setValue(this.__getRoleInfo(1).label);
      }
    },

    __getOptionsMenu: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const accessRights = this.getAccessRights();
      let currentRole = this.__getRoleInfo(1);
      if (this.self().canDelete(accessRights)) {
        currentRole = this.__getRoleInfo(3);
      } else if (this.self().canWrite(accessRights)) {
        currentRole = this.__getRoleInfo(2);
      }

      // promote/demote actions
      switch (currentRole.id) {
        case "read": {
          const promoteButton = new qx.ui.menu.Button(this.tr(`Promote to ${this.__getRoleInfo(2).label}`));
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
          const promoteButton = new qx.ui.menu.Button(this.tr(`Promote to ${this.__getRoleInfo(3).label}`));
          promoteButton.setVisibility(resource === "service" ? "excluded" : "visible");
          promoteButton.addListener("execute", () => {
            this.fireDataEvent("promoteToOwner", {
              gid: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(promoteButton);
          const demoteButton = new qx.ui.menu.Button(this.tr(`Demote to ${this.__getRoleInfo(1).label}`));
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
          const demoteButton = new qx.ui.menu.Button(this.tr(`Demote to ${this.__getRoleInfo(2).label}`));
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

      const removeButton = new qx.ui.menu.Button(this.tr(`Remove ${currentRole.label}`)).set({
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
