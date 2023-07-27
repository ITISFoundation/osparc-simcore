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

    credits: {
      check: "Number",
      nullable: false,
      apply: "__applyCredits"
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
      if (credits !== null) {
        const creditsIndicator = this.getChildControl("credits-indicator");
        creditsIndicator.setCredits(credits);

        this.getChildControl("credits-label").set({
          value: credits + this.tr(" credits")
        });
      }
    },

    // overridden
    _applyAccessRights: function(accessRights) {
      this.base(arguments, accessRights);

      const myGid = osparc.auth.Data.getInstance().getGroupId();
      this.getChildControl("buy-credits-button").set({
        visibility: accessRights && (myGid in accessRights) && accessRights[myGid]["write"] ? "visible" : "hidden"
      });
    },

    // overridden
    _setSubtitle: function() {
      const accessRights = this.getAccessRights();
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const subtitle = this.getChildControl("contact");
      if (myGid in accessRights) {
        if (accessRights[myGid]["delete"]) {
          subtitle.setValue(osparc.data.Roles.WALLET[3].longLabel);
        } else if (accessRights[myGid]["write"]) {
          subtitle.setValue(osparc.data.Roles.WALLET[2].longLabel);
        } else if (accessRights[myGid]["read"]) {
          subtitle.setValue(osparc.data.Roles.WALLET[1].longLabel);
        } else {
          subtitle.setValue(osparc.data.Roles.WALLET[0].longLabel);
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
    }
  }
});
