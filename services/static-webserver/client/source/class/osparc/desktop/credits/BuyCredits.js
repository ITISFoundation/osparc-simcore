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

qx.Class.define("osparc.desktop.credits.BuyCredits", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    this.getChildControl("credits-intro");

    const walletSelectorLayout = this.getChildControl("wallet-selector-layout");
    const walletSelector = walletSelectorLayout.getChildren()[1];
    const walletSelection = walletSelector.getSelection();
    const selectedWalletId = walletSelection && walletSelection.length ? walletSelection[0].walletId : null;
    const walletFound = osparc.desktop.credits.Utils.getWallet(selectedWalletId);
    if (walletFound) {
      this.setWallet(walletFound);
    }

    this.getChildControl("credits-left-view");

    this.__populateLayout();

    const wallets = osparc.store.Store.getInstance().getWallets();
    walletSelector.addListener("changeSelection", e => {
      const selection = e.getData();
      const walletId = selection[0].walletId;
      const found = wallets.find(wallet => wallet.getWalletId() === parseInt(walletId));
      if (found) {
        this.setWallet(found);
      } else {
        this.setWallet(null);
      }
    });
  },

  properties: {
    wallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: false,
      event: "changeWallet",
      apply: "__applyWallet"
    }
  },

  events: {
    "transactionCompleted": "qx.event.type.Event"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "credits-intro":
          control = this.__getCreditsExplanation();
          this._add(control);
          break;
        case "wallet-selector-layout":
          control = osparc.desktop.credits.Utils.createWalletSelectorLayout("read");
          this._add(control);
          break;
        case "credits-left-view":
          control = this.__getCreditsLeftView();
          this._add(control);
          break;
        case "wallet-billing-settings":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(30));
          this._add(control);
          break;
        case "payment-mode-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this.getChildControl("wallet-billing-settings").add(control);
          break;
        case "payment-mode-title":
          control = new qx.ui.basic.Label(this.tr("Payment mode")).set({
            font: "text-14"
          });
          this.getChildControl("payment-mode-layout").add(control);
          break;
        case "payment-mode": {
          this.getChildControl("payment-mode-title");
          control = new qx.ui.form.SelectBox().set({
            allowGrowX: false,
            allowGrowY: false
          });
          const autoItem = new qx.ui.form.ListItem(this.tr("Automatic"), null, "automatic");
          control.add(autoItem);
          const manualItem = new qx.ui.form.ListItem(this.tr("Manual"), null, "manual");
          control.add(manualItem);
          this.getChildControl("payment-mode-layout").add(control);
          break;
        }
        case "one-time-payment":
          control = new osparc.desktop.credits.OneTimePayment().set({
            maxWidth: 300
          });
          this.bind("wallet", control, "wallet");
          control.addListener("transactionCompleted", () => this.fireEvent("transactionCompleted"));
          this.getChildControl("wallet-billing-settings").add(control);
          break;
        case "auto-recharge":
          control = new osparc.desktop.credits.AutoRecharge().set({
            maxWidth: 300
          });
          this.bind("wallet", control, "wallet");
          this.getChildControl("wallet-billing-settings").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __populateLayout: function() {
      const wallet = this.getWallet();
      if (wallet) {
        const paymentMode = this.getChildControl("payment-mode");
        const autoRecharge = this.getChildControl("auto-recharge");
        const oneTime = this.getChildControl("one-time-payment");
        autoRecharge.show();
        oneTime.exclude();
        paymentMode.addListener("changeSelection", e => {
          const model = e.getData()[0].getModel();
          if (model === "manual") {
            autoRecharge.exclude();
            oneTime.show();
          } else {
            autoRecharge.show();
            oneTime.exclude();
          }
        });
      }
    },

    __applyWallet: function(wallet) {
      if (wallet) {
        const walletSelectorLayout = this.getChildControl("wallet-selector-layout");
        const walletSelector = walletSelectorLayout.getChildren()[1];
        walletSelector.getSelectables().forEach(selectable => {
          if (selectable.walletId === wallet.getWalletId()) {
            walletSelector.setSelection([selectable]);
          }
        });
      }
    },

    __getCreditsLeftView: function() {
      const creditsIndicator = new osparc.desktop.credits.CreditsIndicator().set({
        maxWidth: 200
      });
      creditsIndicator.getChildControl("credits-label").set({
        alignX: "left"
      });
      this.bind("wallet", creditsIndicator, "wallet");
      return creditsIndicator;
    },

    __getCreditsExplanation: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20));

      const label = new qx.ui.basic.Label().set({
        value: "Explain here what a Credit is and what one can run/do with them.",
        font: "text-14",
        rich: true,
        wrap: true
      });
      layout.add(label);

      return layout;
    }
  }
});
