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
    }
  },

  events: {
    "openMoreInfo": "qx.event.type.Data"
  },

  members: {
    // overridden
    _getInfoButton: function() {
      const accessRights = this.getAccessRights();
      if (
        ("getRead" in accessRights && accessRights.getRead()) ||
        ("getExecute_access" in accessRights && accessRights.getExecute_access())
      ) {
        const button = this.getChildControl("info-button");
        button.addListener("execute", () => this.fireDataEvent("openMoreInfo", this.getKey()));
        return button;
      }
      return null;
    }
  }
});
