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

  construct: function() {
    this.base(arguments);
  },

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
    }
  },

  events: {
    "promoteToCollaborator": "qx.event.type.Data",
    "promoteToOwner": "qx.event.type.Data",
    "demoteToViewer": "qx.event.type.Data",
    "demoteToCollaborator": "qx.event.type.Data",
    "removeMember": "qx.event.type.Data"
  },

  statics: {
    canDelete: function(accessRights) {
      const canDelete = accessRights.getDelete ? accessRights.getDelete() : false;
      return canDelete;
    },

    canWrite: function(accessRights) {
      let canWrite = accessRights.getWrite ? accessRights.getWrite() : false;
      canWrite = canWrite || (accessRights.getWrite_access ? accessRights.getWrite_access() : false);
      return canWrite;
    },

    canRead: function(accessRights) {
      let canRead = accessRights.getRead ? accessRights.getRead() : false;
      canRead = canRead || (accessRights.getExecute_access ? accessRights.getExecute_access() : false);
      return canRead;
    }
  },

  members: {
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

      this.__setSubtitle();

      const menu = this.__getOptionsMenu();
      const optionsMenu = this.getChildControl("options");
      optionsMenu.setMenu(menu);
    },

    __setSubtitle: function() {
      const accessRights = this.getAccessRights();
      const subtitle = this.getChildControl("contact");
      if (this.self().canDelete(accessRights)) {
        subtitle.setValue(osparc.data.Roles.RESOURCE[3].label);
      } else if (this.self().canWrite(accessRights)) {
        subtitle.setValue(osparc.data.Roles.RESOURCE[2].label);
      } else {
        subtitle.setValue(osparc.data.Roles.RESOURCE[1].label);
      }
    },

    __getOptionsMenu: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const accessRights = this.getAccessRights();
      let currentRole = osparc.data.Roles.RESOURCE[1];
      if (this.self().canDelete(accessRights)) {
        currentRole = osparc.data.Roles.RESOURCE[3];
      } else if (this.self().canWrite(accessRights)) {
        currentRole = osparc.data.Roles.RESOURCE[2];
      }

      // promote/demote actions
      switch (currentRole.id) {
        case "read": {
          const promoteButton = new qx.ui.menu.Button(this.tr("Promote to ") + osparc.data.Roles.RESOURCE[2].label);
          promoteButton.addListener("execute", () => {
            this.fireDataEvent("promoteToCollaborator", {
              gid: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(promoteButton);
          break;
        }
        case "write": {
          const promoteButton = new qx.ui.menu.Button(this.tr("Promote to ") + osparc.data.Roles.RESOURCE[3].label);
          promoteButton.addListener("execute", () => {
            this.fireDataEvent("promoteToOwner", {
              gid: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(promoteButton);
          const demoteButton = new qx.ui.menu.Button(this.tr("Demote to ") + osparc.data.Roles.RESOURCE[1].label);
          demoteButton.addListener("execute", () => {
            this.fireDataEvent("demoteToViewer", {
              gid: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(demoteButton);
          break;
        }
        case "delete": {
          const demoteButton = new qx.ui.menu.Button(this.tr("Demote to ") + osparc.data.Roles.RESOURCE[2].label);
          demoteButton.addListener("execute", () => {
            this.fireDataEvent("demoteToCollaborator", {
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

      const removeButton = new qx.ui.menu.Button(this.tr("Remove ") + currentRole.label).set({
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
