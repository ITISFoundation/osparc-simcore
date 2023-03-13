/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.list.ListItemWithMenu", {
  extend: osparc.ui.list.ListItem,
  type: "abstract",

  properties: {
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

  statics: {
    ICON_SIZE: 24
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "info-button": {
          control = new qx.ui.form.Button().set({
            maxWidth: 28,
            maxHeight: 28,
            alignX: "center",
            alignY: "middle",
            icon: "@MaterialIcons/info_outline/14",
            focusable: false
          });
          this._add(control, {
            row: 0,
            column: 3,
            rowSpan: 2
          });
          break;
        }
        case "options": {
          const iconSize = this.self().ICON_SIZE;
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

    __applyAccessRights: function(value) {
      const optionsMenu = this.getChildControl("options");
      optionsMenu.exclude();

      if (value === null) {
        return;
      }

      this.__setSubtitle();

      this._getInfoButton();

      const menu = this._getOptionsMenu();
      if (menu) {
        optionsMenu.setMenu(menu);
      }
    },

    __setSubtitle: function() {
      const accessRights = this.getAccessRights();
      const subtitle = this.getChildControl("contact");
      if (
        "getDelete" in accessRights && accessRights.getDelete()
      ) {
        subtitle.setValue(osparc.data.Roles.ORG[3].longLabel);
      } else if (
        ("getWrite" in accessRights && accessRights.getWrite()) ||
        ("getWrite_access" in accessRights && accessRights.getWrite_access())
      ) {
        subtitle.setValue(osparc.data.Roles.ORG[2].longLabel);
      } else if (
        ("getRead" in accessRights && accessRights.getRead()) ||
        ("getExecute_access" in accessRights && accessRights.getExecute_access())
      ) {
        subtitle.setValue(osparc.data.Roles.ORG[1].longLabel);
      } else {
        subtitle.setValue(osparc.data.Roles.ORG[0].longLabel);
      }
    },

    _getInfoButton: function() {
      return null;
    },

    _getOptionsMenu: function() {
      return null;
    },

    __applyShowOptions: function(value) {
      const optionsMenu = this.getChildControl("options");
      optionsMenu.setVisibility(value ? "visible" : "excluded");
    }
  }
});
