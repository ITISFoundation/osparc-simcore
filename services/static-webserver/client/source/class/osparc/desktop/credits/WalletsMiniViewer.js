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
      padding: 5,
      margin: 10,
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
    activeWallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: true,
      apply: "__reloadLayout"
    }
  },

  members: {
    __walletListeners: null,

    __buildLayout: function() {
      const store = osparc.store.Store.getInstance();
      store.bind("activeWallet", this, "activeWallet");
      store.addListener("changeWallets", () => this.__reloadLayout());
    },

    __reloadLayout: function() {
      const activeWallet = this.getActiveWallet();
      const preferredWallet = osparc.desktop.credits.Utils.getPreferredWallet();
      const oneWallet = activeWallet ? activeWallet : preferredWallet;
      if (oneWallet) {
        this.__showOneWallet(oneWallet);
      } else {
        this.__showSelectWallet();
      }

      const store = osparc.store.Store.getInstance();
      store.getWallets().forEach(wallet => {
        const preferredWalletId = wallet.addListener("changePreferredWallet", () => this.__reloadLayout());
        this.__walletListeners.push({
          walletId: wallet.getWalletId(),
          listenerId: preferredWalletId
        });
      });
    },

    __removeWallets: function() {
      const store = osparc.store.Store.getInstance();
      this.__walletListeners.forEach(walletListener => {
        const found = store.getWallets().find(wallet => wallet.getWalletId() === walletListener.walletId);
        if (found) {
          found.removeListenerById(walletListener.listenerId);
        }
      });
      this.__walletListeners = [];
      this._removeAll();
    },

    __showSelectWallet: function() {
      this.__removeWallets();

      const iconSrc = "@MaterialIcons/account_balance_wallet/26";
      const walletsButton = new qx.ui.basic.Image(iconSrc).set({
        toolTipText: this.tr("Select Wallet"),
        textColor: "danger-red"
      });
      walletsButton.addListener("tap", () => {
        osparc.desktop.credits.Utils.areWalletsEnabled()
          .then(walletsEnabled => {
            const userCenterWindow = osparc.desktop.credits.UserCenterWindow.openWindow(walletsEnabled);
            userCenterWindow.openWallets();
          });
      }, this);
      this._add(walletsButton, {
        flex: 1
      });
    },

    __showOneWallet: function(wallet) {
      this.__removeWallets();

      this.__addWallet(wallet);
      const changeStatusId = wallet.addListener("changeStatus", () => this.__reloadLayout());
      this.__walletListeners.push({
        walletId: wallet.getWalletId(),
        listenerId: changeStatusId
      });
    },

    __addWallet: function(wallet) {
      const creditsIndicator = new osparc.desktop.credits.CreditsIndicator(wallet);
      creditsIndicator.addListener("tap", () => {
        osparc.desktop.credits.Utils.areWalletsEnabled()
          .then(walletsEnabled => {
            const creditsWindow = osparc.desktop.credits.UserCenterWindow.openWindow(walletsEnabled);
            creditsWindow.openOverview();
          });
      }, this);
      this._add(creditsIndicator, {
        flex: 1
      });
    }
  }
});
