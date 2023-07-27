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

    this.set({
      padding: 5
    });

    this.__walletListeners = [];

    this.__buildLayout();
  },

  properties: {
    currentWallet: {
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
      store.bind("currentWallet", this, "currentWallet");
    },

    __reloadLayout: function() {
      const currentWallet = this.getCurrentWallet();
      if (currentWallet) {
        this.__showOneWallet(currentWallet);
      } else {
        this.__showAllWallets();
      }
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

    __showOneWallet: function(wallet) {
      this.__removeWallets();
      this.__addWallet(wallet);
      const id = wallet.addListener("changeActive", () => this.__reloadLayout());
      this.__walletListeners.push({
        walletId: wallet.getWalletId(),
        listenerId: id
      });
    },

    __showAllWallets: function() {
      this.__removeWallets();
      const store = osparc.store.Store.getInstance();
      store.getWallets().forEach(wallet => {
        if (wallet.isActive()) {
          this.__addWallet(wallet);
        }
        const id = wallet.addListener("changeActive", () => this.__reloadLayout());
        this.__walletListeners.push({
          walletId: wallet.getWalletId(),
          listenerId: id
        });
      });
    },

    __addWallet: function(wallet) {
      const progressBar = new osparc.desktop.credits.CreditsIndicator(wallet, true).set({
        allowShrinkY: true
      });
      this._add(progressBar, {
        flex: 1
      });
    }
  }
});
