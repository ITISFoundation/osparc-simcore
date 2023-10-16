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

qx.Class.define("osparc.desktop.credits.Utils", {
  type: "static",

  statics: {
    areWalletsEnabled: function() {
      const statics = osparc.store.Store.getInstance().get("statics");
      return Boolean(statics && statics["isPaymentEnabled"]);
    },

    creditsToFixed: function(credits) {
      if (credits < 100) {
        return (credits).toFixed(1);
      }
      return parseInt(credits);
    },

    createWalletSelector: function(accessRight = "read", onlyActive = false, emptySelection = false) {
      const store = osparc.store.Store.getInstance();

      const walletSelector = new qx.ui.form.SelectBox();

      const populateSelectBox = selectBox => {
        selectBox.removeAll();

        const wallets = store.getWallets();
        if (emptySelection) {
          const sbItem = new qx.ui.form.ListItem(qx.locale.Manager.tr("Select Credit Account"));
          sbItem.walletId = null;
          selectBox.add(sbItem);
        }
        wallets.forEach(wallet => {
          if (onlyActive && wallet.getStatus() !== "ACTIVE") {
            return;
          }
          const found = wallet.getMyAccessRights();
          if (found && found[accessRight]) {
            const sbItem = new qx.ui.form.ListItem(wallet.getName());
            sbItem.walletId = wallet.getWalletId();
            selectBox.add(sbItem);
          }
        });
      };

      populateSelectBox(walletSelector);
      store.addListener("changeWallets", () => populateSelectBox(walletSelector));

      return walletSelector;
    },

    autoSelectActiveWallet: function(walletSelector) {
      // If there is only one active wallet, select it
      const store = osparc.store.Store.getInstance();
      const wallets = store.getWallets();
      const activeWallets = wallets.filter(wallet => wallet.getStatus() === "ACTIVE");
      if (activeWallets.length === 1) {
        const found = walletSelector.getSelectables().find(sbItem => sbItem.walletId === activeWallets[0].getWalletId());
        if (found) {
          walletSelector.setSelection([found]);
          return true;
        }
      }
      return false;
    },

    getWallet: function(walletId) {
      const store = osparc.store.Store.getInstance();
      const wallets = store.getWallets();
      const foundWallet = wallets.find(wallet => wallet.getWalletId() === walletId);
      if (foundWallet) {
        return foundWallet;
      }
      return null;
    },

    getPreferredWallet: function() {
      const store = osparc.store.Store.getInstance();
      const wallets = store.getWallets();
      const favouriteWallet = wallets.find(wallet => wallet.isPreferredWallet());
      if (favouriteWallet) {
        return favouriteWallet;
      }
      return null;
    },

    getPaymentMethods: function(walletId) {
      return new Promise(resolve => {
        const promises = [];
        if (walletId) {
          const params = {
            url: {
              walletId
            }
          };
          promises.push(osparc.data.Resources.fetch("paymentMethods", "get", params));
        } else {
          const wallets = osparc.store.Store.getInstance().getWallets();
          const myWallets = wallets.filter(wallet => wallet.getMyAccessRights()["write"]);
          myWallets.forEach(myWallet => {
            const params = {
              url: {
                walletId: myWallet.getWalletId()
              }
            };
            promises.push(osparc.data.Resources.fetch("paymentMethods", "get", params));
          });
        }
        Promise.all(promises)
          .then(values => {
            let paymentMethods = [];
            values.forEach(value => paymentMethods = paymentMethods.concat(value));
            resolve(paymentMethods);
          });
      });
    },

    getPaymentMethod: function(paymentMethodId) {
      return new Promise(resolve => {
        this.getPaymentMethods()
          .then(paymentMethods => {
            const paymentMethodFound = paymentMethods.find(paymentMethod => paymentMethod["idr"] === paymentMethodId);
            resolve(paymentMethodFound);
          });
      });
    }
  }
});
