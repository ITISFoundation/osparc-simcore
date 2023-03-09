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
    "openMoreInfo": "qx.event.type.Event"
  },

  members: {
    // overridden
    _getInfoButton: function() {
      const accessRights = this.getAccessRights();
      if (accessRights.getRead()) {
        const button = this.getChildControl("info-button");
        button.addListener("execute", () => this.fireEvent("openMoreInfo", this.getKey()));
        return button;
      }
      return null;
    }
  }
});
