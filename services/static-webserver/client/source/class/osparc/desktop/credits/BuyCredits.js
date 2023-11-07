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

    const store = osparc.store.Store.getInstance();
    store.bind("contextWallet", this, "contextWallet");
  },

  properties: {
    contextWallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: false,
      event: "changeContextWallet",
      apply: "__buildLayout"
    }
  },

  events: {
    "addNewPaymentMethod": "qx.event.type.Event",
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
        case "payment-mode-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._add(control);
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
            margin: 10,
            maxWidth: 400
          });
          this.bind("contextWallet", control, "wallet");
          control.addListener("addNewPaymentMethod", () => this.fireEvent("addNewPaymentMethod"));
          control.addListener("transactionCompleted", () => this.fireEvent("transactionCompleted"));
          this._add(control);
          break;
        case "auto-recharge":
          control = new osparc.desktop.credits.AutoRecharge().set({
            margin: 10,
            maxWidth: 400
          });
          control.addListener("addNewPaymentMethod", () => this.fireEvent("addNewPaymentMethod"));
          this.bind("contextWallet", control, "wallet");
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this._removeAll();
      this._createChildControlImpl("credits-intro");
      const wallet = this.getContextWallet();
      if (wallet.getMyAccessRights()["write"]) {
        this._createChildControlImpl("wallet-billing-settings");
        const paymentMode = this._createChildControlImpl("payment-mode");
        const autoRecharge = this._createChildControlImpl("auto-recharge");
        const oneTime = this._createChildControlImpl("one-time-payment");
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
      } else {
        this._add(osparc.desktop.credits.Utils.getNoWriteAccessOperationsLabel());
      }
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
