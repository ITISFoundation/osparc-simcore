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
    "openEditWallet": "qx.event.type.Data",
    "buyCredits": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "credits-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
            marginLeft: 10,
            alignY: "middle",
            width: 100
          });
          this._add(control, {
            row: 0,
            column: 4,
            rowSpan: 2
          });
          break;
        case "credits-indicator":
          control = new osparc.desktop.credits.CreditsIndicator().set({
            maxHeight: 40
          });
          this.getChildControl("credits-layout").addAt(control, 0);
          break;
        case "credits-label":
          control = new qx.ui.basic.Label();
          this.getChildControl("credits-layout").addAt(control, 1);
          break;
        case "buy-credits-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Buy Credits"),
            icon: "@FontAwesome5Solid/dollar-sign/16",
            maxHeight: 30,
            alignY: "middle",
            visibility: "hidden"
          });
          control.addListener("execute", () => this.fireDataEvent("buyCredits", {
            walletId: this.getKey()
          }), this);
          this._add(control, {
            row: 0,
            column: 5,
            rowSpan: 2
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __applyCredits: function(credits) {
      const creditsIndicator = this.getChildControl("credits-indicator");
      creditsIndicator.setCredits(credits);

      this.getChildControl("credits-label").set({
        value: credits + this.tr(" credits")
      });
    },

    // overridden
    _applyAccessRights: function(accessRights) {
      this.base(arguments, accessRights);

      this.getChildControl("buy-credits-button").set({
        visibility: accessRights["write"] ? "visible" : "hidden"
      });
    },

    // overridden
    _setSubtitle: function() {
      const accessRights = this.getAccessRights();
      const subtitle = this.getChildControl("contact");
      if (accessRights["delete"]) {
        subtitle.setValue(osparc.data.Roles.WALLET[3].longLabel);
      } else if (accessRights["write"]) {
        subtitle.setValue(osparc.data.Roles.WALLET[2].longLabel);
      } else if (accessRights["read"]) {
        subtitle.setValue(osparc.data.Roles.WALLET[1].longLabel);
      } else {
        subtitle.setValue(osparc.data.Roles.WALLET[0].longLabel);
      }
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
