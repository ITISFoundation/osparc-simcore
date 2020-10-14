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

qx.Class.define("osparc.dashboard.CollaboratorListItem", {
  extend: osparc.dashboard.ServiceBrowserListItem,

  construct: function() {
    this.base(arguments);
  },

  properties: {
    collabType: {
      check: [0, 1, 2],
      event: "changeCollabType",
      nullable: true
    },

    accessRights: {
      check: "Object",
      apply: "_applyAccessRights",
      event: "changeAccessRights",
      nullable: true
    },

    showOptions: {
      check: "Boolean",
      apply: "_applyShowOptions",
      event: "changeShowOptions",
      nullable: true
    }
  },

  events: {
    "promoteCollaborator": "qx.event.type.Data",
    "removeCollaborator": "qx.event.type.Data"
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
          osparc.utils.Utils.setIdToWidget(control, "studyItemMenuButton");
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

    // overriden
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

    _applyAccessRights: function(value) {
      if (value === null) {
        return;
      }
      const subtitle = this.getChildControl("contact");
      const isOwner = osparc.component.export.Permissions.canDelete(value);
      const isCollaborator = osparc.component.export.Permissions.canWrite(value);
      if (isOwner) {
        subtitle.setValue(this.tr("Owner"));
      } else if (isCollaborator) {
        subtitle.setValue(this.tr("Collaborator"));
      } else {
        subtitle.setValue(this.tr("Viewer"));
      }
    },

    _applyShowOptions: function(value) {
      const optionsMenu = this.getChildControl("options");
      optionsMenu.setVisibility(value ? "visible" : "excluded");
      if (value) {
        const menu = this.__getOptionsMenu();
        optionsMenu.setMenu(menu);
        optionsMenu.setVisibility(menu.getChildren().length ? "visible" : "excluded");
      }
    },

    __getOptionsMenu: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const accessRights = this.getAccessRights();
      if (!osparc.component.export.Permissions.canDelete(accessRights) && this.getCollabType() === 2) {
        const makeOwnerButton = new qx.ui.menu.Button(this.tr("Make Owner"));
        makeOwnerButton.addListener("execute", () => {
          this.fireDataEvent("promoteCollaborator", {
            gid: this.getKey(),
            name: this.getTitle()
          });
        });
        menu.add(makeOwnerButton);
      }

      if (!osparc.component.export.Permissions.canDelete(accessRights)) {
        const removeButton = new qx.ui.menu.Button(this.tr("Remove Collaborator"));
        removeButton.addListener("execute", () => {
          this.fireDataEvent("removeCollaborator", {
            gid: this.getKey(),
            name: this.getTitle()
          });
        });
        menu.add(removeButton);
      }

      return menu;
    }
  }
});
