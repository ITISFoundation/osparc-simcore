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
    walletType: {
      check: ["personal", "shared"],
      init: "personal",
      nullable: false,
      apply: "__setDefaultThumbnail"
    },

    creditsAvailable: {
      check: "Number",
      nullable: false,
      apply: "__applyCreditsAvailable"
    },

    status: {
      check: ["ACTIVE", "INACTIVE"],
      init: null,
      nullable: false,
      apply: "__applyStatus"
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
        case "status-button":
          control = new qx.ui.form.Button().set({
            maxHeight: 30,
            width: 62,
            alignX: "center",
            alignY: "middle",
            enabled: false
          });
          control.addListener("execute", () => {
            const walletId = this.getKey();
            const store = osparc.store.Store.getInstance();
            const found = store.getWallets().find(wallet => wallet.getWalletId() === parseInt(walletId));
            if (found) {
              // switch status
              found.setStatus(found.getStatus() === "ACTIVE" ? "INACTIVE" : "ACTIVE");
            }
          }, this);
          this._add(control, {
            row: 0,
            column: 5,
            rowSpan: 2
          });
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
            column: 6,
            rowSpan: 2
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __applyCredits: function(creditsAvailable) {
      if (creditsAvailable !== null) {
        const creditsIndicator = this.getChildControl("credits-indicator");
        creditsIndicator.setCreditsAvailable(creditsAvailable);

        this.getChildControl("credits-label").set({
          value: creditsAvailable + this.tr(" credits")
        });
      }
    },

    __canIWrite: function() {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const accessRights = this.getAccessRights();
      return (accessRights && (myGid in accessRights) && accessRights[myGid]["write"]);
    },

    // overridden
    _applyAccessRights: function(accessRights) {
      this.base(arguments, accessRights);

      this.getChildControl("buy-credits-button").set({
        visibility: this.__canIWrite() ? "visible" : "hidden"
      });
    },

    // overridden
    _setSubtitle: function() {
      const accessRights = this.getAccessRights();
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const subtitle = this.getChildControl("contact");
      if (myGid in accessRights) {
        if (accessRights[myGid]["write"]) {
          subtitle.setValue(osparc.data.Roles.WALLET[2].longLabel);
        } else if (accessRights[myGid]["read"]) {
          subtitle.setValue(osparc.data.Roles.WALLET[1].longLabel);
        }
      }
    },

    // overridden
    _getOptionsMenu: function() {
      let menu = null;
      const accessRights = this.getAccessRights();
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      if ((myGid in accessRights) && accessRights[myGid]["write"]) {
        const optionsMenu = this.getChildControl("options");
        optionsMenu.show();

        menu = new qx.ui.menu.Menu().set({
          position: "bottom-right"
        });

        const editWalletButton = new qx.ui.menu.Button(this.tr("Edit details..."));
        editWalletButton.addListener("execute", () => this.fireDataEvent("openEditWallet", this.getKey()));
        menu.add(editWalletButton);
      }
      return menu;
    },

    // overridden
    _applyThumbnail: function(value) {
      const thumbnail = this.getChildControl("thumbnail");
      if (value) {
        thumbnail.setSource(value);
      } else {
        this.__setDefaultThumbnail();
      }
    },

    __setDefaultThumbnail: function() {
      if (this.getThumbnail() === null) {
        // default thumbnail only if it's null
        const thumbnail = this.getChildControl("thumbnail");
        if (this.getWalletType() === "personal") {
          thumbnail.setSource(osparc.utils.Icons.user(osparc.ui.list.ListItemWithMenu.ICON_SIZE));
        } else {
          thumbnail.setSource(osparc.utils.Icons.organization(osparc.ui.list.ListItemWithMenu.ICON_SIZE));
        }
      }
    },

    __applyStatus: function(status) {
      if (status) {
        const statusButton = this.getChildControl("status-button");
        statusButton.set({
          icon: status === "ACTIVE" ? "@FontAwesome5Solid/toggle-on/16" : "@FontAwesome5Solid/toggle-off/16",
          label: status === "ACTIVE" ? this.tr("ON") : this.tr("OFF"),
          toolTipText: status === "ACTIVE" ? this.tr("Wallet enabled") : this.tr("Wallet blocked"),
          enabled: this.__canIWrite()
        });
      }
    }
  }
});
