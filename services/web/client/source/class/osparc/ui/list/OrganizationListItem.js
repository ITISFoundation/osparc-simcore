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

qx.Class.define("osparc.ui.list.OrganizationListItem", {
  extend: osparc.ui.list.ListItem,

  construct: function() {
    this.base(arguments);
  },

  properties: {
    accessRights: {
      check: "Object",
      nullable: false,
      apply: "_applyAccessRights",
      event: "changeAcessRights"
    }
  },

  events: {
    "openEditOrganization": "qx.event.type.Data",
    "deleteOrganization": "qx.event.type.Data"
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

    _applyAccessRights: function(value) {
      if (value === null) {
        return;
      }
      if (value.getDelete()) {
        const optionsMenu = this.getChildControl("options");
        const menu = this.__getOptionsMenu();
        optionsMenu.setMenu(menu);
      }
    },

    __getOptionsMenu: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const editOrgButton = new qx.ui.menu.Button(this.tr("Edit details"));
      editOrgButton.addListener("execute", () => {
        this.fireDataEvent("openEditOrganization", this.getKey());
      });
      menu.add(editOrgButton);

      const deleteOrgButton = new qx.ui.menu.Button(this.tr("Delete"));
      deleteOrgButton.addListener("execute", () => {
        this.fireDataEvent("deleteOrganization", this.getKey());
      });
      menu.add(deleteOrgButton);

      return menu;
    },

    // overridden
    _applyThumbnail: function(value) {
      const thumbnail = this.getChildControl("thumbnail");
      if (value) {
        thumbnail.setSource(value);
      } else {
        thumbnail.setSource("@FontAwesome5Solid/users/24");
      }
    }
  }
});
