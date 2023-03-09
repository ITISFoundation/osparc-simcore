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
    _getOptionsMenu: function() {
      let menu = null;
      const accessRights = this.getAccessRights();
      if (accessRights.getRead()) {
        const optionsMenu = this.getChildControl("options");
        optionsMenu.show();

        menu = new qx.ui.menu.Menu().set({
          position: "bottom-right"
        });

        const moreInfoButton = new qx.ui.menu.Button(this.tr("More Info..."));
        moreInfoButton.addListener("execute", () => this.fireEvent("openMoreInfo", this.getKey()));
        menu.add(moreInfoButton);
      }
      return menu;
    }
  }
});
