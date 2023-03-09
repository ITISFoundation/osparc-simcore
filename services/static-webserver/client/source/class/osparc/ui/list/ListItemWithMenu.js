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

      const menu = this._getOptionsMenu();
      if (menu) {
        optionsMenu.setMenu(menu);
      }
    },

    __setSubtitle: function() {
      const accessRights = this.getAccessRights();
      const subtitle = this.getChildControl("contact");
      if (accessRights.getDelete()) {
        subtitle.setValue(osparc.data.Roles.ORG[3].longLabel);
      } else if (accessRights.getWrite()) {
        subtitle.setValue(osparc.data.Roles.ORG[2].longLabel);
      } else if (accessRights.getRead()) {
        subtitle.setValue(osparc.data.Roles.ORG[1].longLabel);
      } else {
        subtitle.setValue(osparc.data.Roles.ORG[0].longLabel);
      }
    },

    _getOptionsMenu: function() {
      throw new Error("Abstract method called!");
    },

    __applyShowOptions: function(value) {
      const optionsMenu = this.getChildControl("options");
      optionsMenu.setVisibility(value ? "visible" : "excluded");
    }
  }
});
