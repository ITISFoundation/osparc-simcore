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
  extend: osparc.ui.list.ListItem,

  properties: {
    accessRights: {
      check: "Object",
      nullable: false,
      apply: "__applyAccessRights",
      event: "changeAccessRights"
    }
  },

  events: {
    "openEditOrganization": "qx.event.type.Data",
    "deleteOrganization": "qx.event.type.Data"
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

    __applyAccessRights: function(accessRights) {
      const optionsMenu = this.getChildControl("options");
      optionsMenu.exclude();
      if (accessRights === null) {
        return;
      }
      if (accessRights.getWrite()) {
        optionsMenu.show();
        const menu = this.__getOptionsMenu(accessRights);
        optionsMenu.setMenu(menu);
      }
    },

    __getOptionsMenu: function(accessRights) {
      const menu = new qx.ui.menu.Menu().set({
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
        deleteOrgButton.addListener("execute", () => {
          this.fireDataEvent("deleteOrganization", this.getKey());
        });
        menu.add(deleteOrgButton);
      }

      return menu;
    },

    // overridden
    _applyThumbnail: function(value) {
      const thumbnail = this.getChildControl("thumbnail");
      if (value) {
        thumbnail.setSource(value);
      } else {
        thumbnail.setSource(osparc.utils.Icons.organization(this.self().ICON_SIZE));
      }
      if (this.isPropertyInitialized("key")) {
        const store = osparc.store.Store.getInstance();
        store.getProductEveryone()
          .then(groupProductEveryone => {
            if (groupProductEveryone && parseInt(this.getKey()) === groupProductEveryone["gid"]) {
              thumbnail.setSource(osparc.utils.Icons.everyone(this.self().ICON_SIZE));
            }
          });
      }
    }
  }
});
