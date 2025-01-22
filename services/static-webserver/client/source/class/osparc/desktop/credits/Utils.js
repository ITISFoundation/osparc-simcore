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
    DANGER_ZONE: 25, // one hour consumption
    CREDITS_ICON: "@FontAwesome5Solid/database/",

    creditsUpdated: function(walletId, credits) {
      const store = osparc.store.Store.getInstance();
      const walletFound = store.getWallets().find(wallet => wallet.getWalletId() === parseInt(walletId));
      if (walletFound) {
        walletFound.setCreditsAvailable(parseFloat(credits));
      }
    },

    openBuyCredits: function(paymentMethods = []) {
      const buyView = new osparc.desktop.credits.BuyCreditsStepper(
        paymentMethods.map(({idr, cardHolderName, cardNumberMasked}) => ({
          label: `${cardHolderName} ${cardNumberMasked}`,
          id: idr
        }))
      );
      const win = osparc.ui.window.Window.popUpInWindow(buyView, "Buy credits", 400, 600).set({
        resizable: false,
        movable: false
      });
      buyView.addListener("completed", () => win.close());
      win.addListener("close", () => buyView.cancelPayment())
      return {
        window: win,
        buyCreditsWidget: buyView,
      };
    },


    areWalletsEnabled: function() {
      const statics = osparc.store.Store.getInstance().get("statics");
      return Boolean(statics && statics["isPaymentEnabled"]);
    },

    getNoWriteAccessInformationLabel: function() {
      return new qx.ui.basic.Label().set({
        value: qx.locale.Manager.tr("You can't access this information"),
        font: "text-14",
        allowGrowX: true
      });
    },

    getNoWriteAccessOperationsLabel: function() {
      return new qx.ui.basic.Label().set({
        value: qx.locale.Manager.tr("You can't access these operations"),
        font: "text-14",
        allowGrowX: true
      });
    },

    creditsToColor: function(credits, defaultColor = "text") {
      const preferencesSettings = osparc.Preferences.getInstance();
      let color = defaultColor;
      const dangerZone = this.DANGER_ZONE;
      if (credits <= dangerZone) {
        color = "danger-red";
      } else if (credits <= preferencesSettings.getCreditsWarningThreshold()) {
        color = "warning-yellow";
      }
      return color;
    },

    normalizeCredits: function(credits) {
      const logBase = (n, base) => Math.log(n) / Math.log(base);

      let normalized = logBase(credits, 10000) + 0.01;
      normalized = Math.min(Math.max(normalized, 0), 1);
      return normalized * 100;
    },

    creditsToFixed: function(credits) {
      if (credits < 10) {
        return (credits).toFixed(1);
      }
      return parseInt(credits);
    },

    createWalletSelector: function(accessRight = "read") {
      const store = osparc.store.Store.getInstance();

      const walletSelector = new qx.ui.form.SelectBox().set({
        maxWidth: 250
      });

      const populateSelectBox = selectBox => {
        selectBox.removeAll();

        const wallets = store.getWallets();
        wallets.forEach(wallet => {
          const found = wallet.getMyAccessRights();
          if (found && found[accessRight]) {
            const sbItem = new qx.ui.form.ListItem(`${wallet.getName()} (${wallet.getCreditsAvailable()} credits)`);
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

    populatePaymentMethodSelector: function(wallet, paymentMethodSB) {
      paymentMethodSB.removeAll();
      return new Promise(resolve => {
        osparc.desktop.credits.Utils.getPaymentMethods(wallet.getWalletId())
          .then(paymentMethods => {
            paymentMethods.forEach(paymentMethod => {
              let label = paymentMethod.cardHolderName;
              label += " ";
              label += paymentMethod.cardNumberMasked.substr(paymentMethod.cardNumberMasked.length - 9);
              const lItem = new qx.ui.form.ListItem(label, null, paymentMethod.idr);
              paymentMethodSB.add(lItem);
            });
          })
          .finally(() => resolve());
      });
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

    getMyWallets: function() {
      const store = osparc.store.Store.getInstance();
      const wallets = store.getWallets();
      const myWallets = wallets.filter(wallet => wallet.getMyAccessRights()["write"]);
      if (myWallets) {
        return myWallets;
      }
      return [];
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
          const myWallets = this.getMyWallets();
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
