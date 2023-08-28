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

qx.Class.define("osparc.desktop.organizations.SharedResourceListItem", {
  extend: osparc.ui.list.ListItemWithMenu,

  properties: {
    orgId: {
      check: "Integer",
      init: true,
      nullable: false,
      event: "changeOrgId"
    },

    version: {
      check: "String",
      init: true,
      nullable: true,
      event: "changeVersion"
    }
  },

  events: {
    "openMoreInfo": "qx.event.type.Data"
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
            column: 4,
            rowSpan: 2
          });
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    // overridden
    _getInfoButton: function() {
      const accessRights = this.getAccessRights();
      if (
        ("getRead" in accessRights && accessRights.getRead()) ||
        ("getExecute_access" in accessRights && accessRights.getExecute_access())
      ) {
        const button = this.getChildControl("info-button");
        button.addListener("execute", () => this.fireDataEvent("openMoreInfo", {
          key: this.getKey(),
          version: this.getVersion()
        }));
        return button;
      }
      return null;
    }
  }
});
