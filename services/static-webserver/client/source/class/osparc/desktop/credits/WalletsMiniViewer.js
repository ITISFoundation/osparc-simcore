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
      cursor: "pointer",
      padding: 5,
      paddingRight: 10
    });

    this.__walletListeners = [];

    this.__buildLayout();

    this.addListener("tap", () => {
      osparc.desktop.credits.Utils.areWalletsEnabled()
        .then(walletsEnabled => {
          const creditsWindow = osparc.desktop.credits.CreditsWindow.openWindow(walletsEnabled);
          creditsWindow.openOverview();
        });
    }, this);
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
      const preferredWallet = osparc.desktop.credits.Utils.getFavouriteWallet();
      const oneWallet = activeWallet ? activeWallet : preferredWallet;
      if (oneWallet) {
        this.__showOneWallet(oneWallet);
      } else if (osparc.store.Store.getInstance().getWallets().length) {
        this.__showAllWallets();
      } else {
        this.__showNoWallets();
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

    __showNoWallets: function() {
      this.__removeWallets();

      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const iconSrc = "@MaterialIcons/account_balance_wallet/26";
      const walletsButton = new qx.ui.form.Button(null, iconSrc).set({
        toolTipText: this.tr("No Wallets"),
        backgroundColor: "transparent",
        textColor: "danger-red"
      });
      walletsButton.addListener("tap", () => {
        osparc.desktop.credits.Utils.areWalletsEnabled()
          .then(walletsEnabled => {
            const creditsWindow = osparc.desktop.credits.CreditsWindow.openWindow(walletsEnabled);
            creditsWindow.openWallets();
          });
      }, this);
      this._add(walletsButton, {
        flex: 1
      });

      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });
    },

    __showOneWallet: function(wallet) {
      this.__removeWallets();

      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      this.__addWallet(wallet);
      this.__addWalletListener(wallet);

      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });
    },

    __showAllWallets: function() {
      this.__removeWallets();

      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const wallets = osparc.store.Store.getInstance().getWallets();
      const maxIndicators = 3;
      for (let i=0; i<wallets.length && i<maxIndicators; i++) {
        const wallet = wallets[i];
        if (wallet.getStatus() === "ACTIVE") {
          this.__addWallet(wallet);
        }
        this.__addWalletListener(wallet);
      }

      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });
    },

    __addWallet: function(wallet) {
      const progressBar = new osparc.desktop.credits.CreditsIndicator(wallet).set({
        allowShrinkY: true
      });
      this._add(progressBar, {
        flex: 1
      });
    },

    __addWalletListener: function(wallet) {
      const changeStatusId = wallet.addListener("changeStatus", () => this.__reloadLayout());
      this.__walletListeners.push({
        walletId: wallet.getWalletId(),
        listenerId: changeStatusId
      });

      const preferredWalletId = wallet.addListener("changePreferredWallet", () => this.__reloadLayout());
      this.__walletListeners.push({
        walletId: wallet.getWalletId(),
        listenerId: preferredWalletId
      });
    }
  }
});
