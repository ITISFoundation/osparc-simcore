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
    credits: {
      check: "Number",
      apply: "__applyCredits",
      nullable: false
    }
  },

  events: {
    "openEditWallet": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "credits-indicator": {
          control = osparc.desktop.credits.CreditsLeft.createCreditsLeftInidcator().set({
            merginLeft: 10,
            maxHeight: 40
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

    __applyCredits: function(credits) {
      const creditsIndicator = this.getChildControl("credits-indicator");
      const val = osparc.desktop.credits.CreditsLeft.convertCreditsToIndicatorValue(credits);
      creditsIndicator.setValue(val);
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
          const editWalletButton = new qx.ui.menu.Button(this.tr("Edit details..."));
          editWalletButton.addListener("execute", () => this.fireDataEvent("openEditWallet", this.getKey()));
          menu.add(editWalletButton);
        }
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
