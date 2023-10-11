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

    const grid = new qx.ui.layout.Grid(80, 50);
    grid.setColumnMaxWidth(0, 400);
    grid.setColumnMaxWidth(1, 400);
    this._setLayout(grid);

    this.__buildLayout();
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
        case "wallet-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
          this._add(control, {
            row: 0,
            column: 0
          });
          break;
        case "explanation-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
          this._add(control, {
            row: 0,
            column: 1
          });
          break;
        case "one-time-payment":
          control = new osparc.desktop.credits.OneTimePayment();
          this.bind("wallet", control, "wallet");
          control.addListener("transactionCompleted", () => this.fireEvent("transactionCompleted"));
          this._add(control, {
            row: 1,
            column: 0
          });
          break;
        case "auto-recharge-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(15));
          this._add(control, {
            row: 1,
            column: 1
          });
          break;
        case "wallet-info": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          const label = new qx.ui.basic.Label().set({
            value: this.tr("Credit Account:"),
            font: "text-14"
          });
          control.add(label);
          this.getChildControl("wallet-layout").add(control);
          break;
        }
        case "wallet-selector":
          control = this.__getWalletSelector();
          this.getChildControl("wallet-info").add(control);
          break;
        case "credits-left-view":
          control = this.__getCreditsLeftView();
          this.getChildControl("wallet-info").add(control);
          break;
        case "credits-explanation":
          control = this.__getCreditsExplanation();
          this.getChildControl("explanation-layout").add(control);
          break;
        case "auto-recharge-title":
          control = new qx.ui.basic.Label().set({
            value: this.tr("Auto recharge:"),
            font: "text-16"
          });
          this.getChildControl("auto-recharge-layout").add(control);
          break;
        case "auto-recharge-description":
          control = new qx.ui.basic.Label().set({
            value: this.tr("Keep your balance running smoothly by automatically setting your credits to be recharged when it runs low."),
            font: "text-14",
            rich: true,
            wrap: true
          });
          this.getChildControl("auto-recharge-layout").add(control);
          break;
        case "auto-recharge-options":
          control = this.__getAutoRechargeOptions();
          this.getChildControl("auto-recharge-layout").add(control);
          break;
        case "auto-recharge-button":
          control = this.__getAutoRechargeButton();
          this.getChildControl("auto-recharge-layout").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyWallet: function(wallet) {
      let myAccessRights = null;
      if (wallet) {
        const walletSelector = this.getChildControl("wallet-selector");
        walletSelector.getSelectables().forEach(selectable => {
          if (selectable.walletId === wallet.getWalletId()) {
            walletSelector.setSelection([selectable]);
          }
        });
        myAccessRights = wallet.getMyAccessRights();
      }
      this.getChildControl("auto-recharge-button").set({
        enabled: Boolean(myAccessRights && myAccessRights["write"])
      });
    },

    __buildLayout: function() {
      this.getChildControl("wallet-selector");
      this.getChildControl("credits-left-view");
      this.getChildControl("one-time-payment");
      this.getChildControl("credits-explanation");
      this.__buildAutoRecharge();
    },

    __buildAutoRecharge: function() {
      this.getChildControl("auto-recharge-title");
      this.getChildControl("auto-recharge-description");
      this.getChildControl("auto-recharge-options");
      this.getChildControl("auto-recharge-button");
    },

    __getWalletSelector: function() {
      const walletSelector = osparc.desktop.credits.Utils.createWalletSelector("write", false, false);

      walletSelector.addListener("changeSelection", e => {
        const selection = e.getData();
        if (selection.length) {
          const store = osparc.store.Store.getInstance();
          const found = store.getWallets().find(wallet => wallet.getWalletId() === parseInt(selection[0].walletId));
          if (found) {
            this.setWallet(found);
          }
        }
      });

      if (walletSelector.getSelectables().length) {
        walletSelector.setSelection([walletSelector.getSelectables()[0]]);
      }

      return walletSelector;
    },

    __getCreditsLeftView: function() {
      const creditsIndicator = new osparc.desktop.credits.CreditsIndicator();
      creditsIndicator.getChildControl("credits-label").set({
        alignX: "left"
      });
      this.bind("wallet", creditsIndicator, "wallet");
      return creditsIndicator;
    },

    __getCreditsExplanation: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20));

      const label1 = new qx.ui.basic.Label().set({
        value: "Explain here what a Credit is and what one can run/do with them.",
        font: "text-16",
        rich: true,
        wrap: true
      });
      layout.add(label1);

      const label2 = new qx.ui.basic.Label().set({
        value: "<i>If something goes wrong you won't be charged</i>",
        font: "text-16",
        rich: true,
        wrap: true
      });
      layout.add(label2);

      return layout;
    },

    __getAutoRechargeOptions: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const lowerThresholdLabel = new qx.ui.basic.Label().set({
        value: this.tr("When balance goes below ($):"),
        font: "text-14"
      });
      layout.add(lowerThresholdLabel);

      const lowerThresholdField = new qx.ui.form.TextField().set({
        maxWidth: 100,
        textAlign: "center",
        font: "text-14"
      });
      layout.add(lowerThresholdField);

      const balanceBackLabel = new qx.ui.basic.Label().set({
        value: this.tr("Top up with ($):"),
        font: "text-14"
      });
      layout.add(balanceBackLabel);

      const paymentAmountField = new qx.ui.form.TextField().set({
        maxWidth: 100,
        textAlign: "center",
        font: "text-14"
      });
      layout.add(paymentAmountField);

      const label = new qx.ui.basic.Label().set({
        value: this.tr("Payment Method:"),
        font: "text-14"
      });
      layout.add(label);

      const paymentMethods = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      layout.add(paymentMethods);

      return layout;
    },

    __getAutoRechargeButton: function() {
      const autoRechargeBtn = new osparc.ui.form.FetchButton().set({
        label: this.tr("Enable Auto Recharge"),
        font: "text-16",
        appearance: "strong-button",
        maxWidth: 200,
        center: true
      });
      return autoRechargeBtn;
    }
  }
});
