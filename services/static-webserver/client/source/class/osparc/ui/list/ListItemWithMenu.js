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

      this._setSubtitle();

      this._getInfoButton();
    },

    _setSubtitle: function() {
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
