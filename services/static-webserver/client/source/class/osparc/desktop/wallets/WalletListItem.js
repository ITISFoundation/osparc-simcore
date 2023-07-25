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

qx.Class.define("osparc.desktop.wallets.WalletListItem", {
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
    "openEditWallet": "qx.event.type.Data",
    "deleteWallet": "qx.event.type.Data"
  },

  members: {
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
          const editWalletButton = new qx.ui.menu.Button(this.tr("Edit details..."));
          editWalletButton.addListener("execute", () => this.fireDataEvent("openEditWallet", this.getKey()));
          menu.add(editWalletButton);
        }

        if (accessRights["delete"]) {
          const deleteWalletButton = new qx.ui.menu.Button(this.tr("Delete"));
          this.bind("showDeleteButton", deleteWalletButton, "visibility", {
            converter: show => show ? "visible" : "excluded"
          });
          deleteWalletButton.addListener("execute", () => this.fireDataEvent("deleteWallet", this.getKey()));
          menu.add(deleteWalletButton);
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
