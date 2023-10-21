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

qx.Class.define("osparc.desktop.credits.WalletsMiniViewer", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(3));

    osparc.utils.Utils.setIdToWidget(this, "walletsMiniViewer");

    this.set({
      alignX: "center",
      padding: 4,
      margin: 6,
      marginRight: 20
    });

    // make it look like a button
    this.set({
      cursor: "pointer",
      backgroundColor: "background-main-3"
    });
    this.addListener("pointerover", () => this.setBackgroundColor("background-main-4"), this);
    this.addListener("pointerout", () => this.setBackgroundColor("background-main-3"), this);
    this.getContentElement().setStyles({
      "border-radius": "4px"
    });

    this.__walletListeners = [];

    this.__buildLayout();
  },

  properties: {
    contextWallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: true,
      apply: "__reloadLayout"
    }
  },

  members: {
    __buildLayout: function() {
      const store = osparc.store.Store.getInstance();
      store.bind("contextWallet", this, "contextWallet");
    },

    __reloadLayout: function() {
      this._removeAll();
      const contextWallet = this.getContextWallet();
      if (contextWallet) {
        this.__showOneWallet(contextWallet);
      } else {
        this.__showSelectWallet();
      }
    },

    __showOneWallet: function(wallet) {
      const creditsIndicator = new osparc.desktop.credits.CreditsIndicator(wallet);
      creditsIndicator.addListener("tap", () => {
        const walletsEnabled = osparc.desktop.credits.Utils.areWalletsEnabled();
        if (walletsEnabled) {
          const creditsWindow = osparc.desktop.credits.UserCenterWindow.openWindow();
          creditsWindow.openOverview();
        }
      }, this);
      this._add(creditsIndicator, {
        flex: 1
      });
    },

    __showSelectWallet: function() {
      const iconSrc = "@MaterialIcons/account_balance_wallet/26";
      const walletsButton = new qx.ui.basic.Image(iconSrc).set({
        toolTipText: this.tr("Select Credit Account"),
        textColor: "danger-red"
      });
      walletsButton.addListener("tap", () => {
        const walletsEnabled = osparc.desktop.credits.Utils.areWalletsEnabled();
        if (walletsEnabled) {
          const userCenterWindow = osparc.desktop.credits.UserCenterWindow.openWindow();
          userCenterWindow.openWallets();
        }
      }, this);
      this._add(walletsButton, {
        flex: 1
      });
    }
  }
});
