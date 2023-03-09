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
  extend: osparc.ui.list.ListItemWithMenu,

  properties: {
    showDeleteButton: {
      check: "Boolean",
      init: true,
      nullable: false,
      event: "changeShowDeleteButton"
    }
  },

  events: {
    "openEditOrganization": "qx.event.type.Data",
    "deleteOrganization": "qx.event.type.Data"
  },

  members: {
    // overridden
    _getOptionsMenu: function() {
      let menu = null;
      const accessRights = this.getAccessRights();
      if (accessRights.getWrite()) {
        const optionsMenu = this.getChildControl("options");
        optionsMenu.show();

        menu = new qx.ui.menu.Menu().set({
          position: "bottom-right"
        });

        if (accessRights.getWrite()) {
          const editOrgButton = new qx.ui.menu.Button(this.tr("Edit details..."));
          editOrgButton.addListener("execute", () => {
            this.fireDataEvent("openEditOrganization", this.getKey());
          });
          menu.add(editOrgButton);
        }

        if (accessRights.getDelete()) {
          const deleteOrgButton = new qx.ui.menu.Button(this.tr("Delete"));
          this.bind("showDeleteButton", deleteOrgButton, "visibility", {
            converter: show => show ? "visible" : "excluded"
          });
          deleteOrgButton.addListener("execute", () => {
            this.fireDataEvent("deleteOrganization", this.getKey());
          });
          menu.add(deleteOrgButton);
        }
        optionsMenu.setMenu(menu);
      }
      return menu;
    },

    // overridden
    _applyThumbnail: function(value) {
      const thumbnail = this.getChildControl("thumbnail");
      if (value) {
        thumbnail.setSource(value);
      } else {
        thumbnail.setSource(osparc.utils.Icons.organization(osparc.ui.list.ListItemWithMenu.ICON_SIZE));
      }
      if (this.isPropertyInitialized("key")) {
        const store = osparc.store.Store.getInstance();
        store.getProductEveryone()
          .then(groupProductEveryone => {
            if (groupProductEveryone && parseInt(this.getKey()) === groupProductEveryone["gid"]) {
              thumbnail.setSource(osparc.utils.Icons.everyone(osparc.ui.list.ListItemWithMenu.ICON_SIZE));
            }
          });
      }
    }
  }
});
