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
    },

    groupMembers: {
      check: "Object",
      nullable: true,
      init: null,
      event: "changeGroupMembers",
      apply: "updateNMembers",
    },
  },

  events: {
    "openEditOrganization": "qx.event.type.Data",
    "deleteOrganization": "qx.event.type.Data"
  },

  members: {
    // overridden
    _setRole: function() {
      // Role field was already filled up with the nMembers
      return;
    },

    updateNMembers: function() {
      const roleText = this.getGroupMembers() ? Object.keys(this.getGroupMembers()).length + this.tr(" members") : "-";
      this.setRole(roleText);
    },

    // overridden
    _getOptionsMenu: function() {
      let menu = null;
      const accessRights = this.getAccessRights();
      if (accessRights["write"]) {
        const optionsMenu = this.getChildControl("options");
        optionsMenu.show();

        menu = new qx.ui.menu.Menu().set({
          position: "bottom-right"
        });

        if (accessRights["write"]) {
          const editOrgButton = new qx.ui.menu.Button(this.tr("Edit details..."));
          editOrgButton.addListener("execute", () => {
            this.fireDataEvent("openEditOrganization", this.getKey());
          });
          menu.add(editOrgButton);
        }

        if (accessRights["delete"]) {
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
        const groupsStore = osparc.store.Groups.getInstance();
        const groupProductEveryone = groupsStore.getEveryoneProductGroup();
        if (groupProductEveryone && parseInt(this.getKey()) === groupProductEveryone.getGroupId()) {
          thumbnail.setSource(osparc.utils.Icons.everyone(osparc.ui.list.ListItemWithMenu.ICON_SIZE));
        }
      }
    },
  }
});
