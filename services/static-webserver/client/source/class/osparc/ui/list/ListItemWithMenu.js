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
      apply: "_applyAccessRights",
      event: "changeAccessRights",
      nullable: true
    },

    showOptions: {
      check: "Boolean",
      apply: "__applyShowOptions",
      event: "changeShowOptions",
      nullable: true
    },

    options: {
      check: "Array",
      nullable: true,
      event: "changeOptions",
      apply: "__applyOptions"
    }
  },

  statics: {
    ICON_SIZE: 24
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
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

    _applyAccessRights: function(value) {
      const optionsMenu = this.getChildControl("options");
      optionsMenu.hide();

      if (value === null) {
        return;
      }

      this._getInfoButton();

      this.__applyOptions();
    },

    _setSubtitle: function() {
      const accessRights = this.getAccessRights();
      const subtitle = this.getChildControl("contact");
      if (
        "getDelete" in accessRights && accessRights.getDelete()
      ) {
        subtitle.setValue(osparc.data.Roles.ORG[3].label);
      } else if (
        ("getWrite" in accessRights && accessRights.getWrite()) ||
        ("getWriteAccess" in accessRights && accessRights.getWriteAccess())
      ) {
        subtitle.setValue(osparc.data.Roles.ORG[2].label);
      } else if (
        ("getRead" in accessRights && accessRights.getRead()) ||
        ("getExecuteAccess" in accessRights && accessRights.getExecuteAccess())
      ) {
        subtitle.setValue(osparc.data.Roles.ORG[1].label);
      } else {
        subtitle.setValue(osparc.data.Roles.ORG[0].label);
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
      optionsMenu.setVisibility(value ? "visible" : "hidden");
    },

    __applyOptions: function() {
      const menu = this._getOptionsMenu();
      if (menu && menu.getChildren() && menu.getChildren().length) {
        const optionsMenu = this.getChildControl("options");
        optionsMenu.setMenu(menu);
      }
    }
  }
});
