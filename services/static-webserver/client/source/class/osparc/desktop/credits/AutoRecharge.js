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

qx.Class.define("osparc.desktop.credits.AutoRecharge", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    this.__buildLayout();
  },

  properties: {
    wallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: true,
      event: "changeWallet",
      apply: "__applyWallet"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "auto-recharge-title":
          control = new qx.ui.basic.Label().set({
            value: this.tr("Auto recharge:"),
            font: "text-16"
          });
          this._add(control);
          break;
        case "auto-recharge-description":
          control = new qx.ui.basic.Label().set({
            value: this.tr("Keep your balance running smoothly by automatically setting your credits to be recharged when it runs low."),
            font: "text-14",
            rich: true,
            wrap: true
          });
          this._add(control);
          break;
        case "auto-recharge-options":
          control = this.__getAutoRechargeOptions();
          this._add(control);
          break;
        case "auto-recharge-button":
          control = this.__getAutoRechargeButton();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyWallet: function(wallet) {
      let myAccessRights = null;
      if (wallet) {
        myAccessRights = wallet.getMyAccessRights();
      }
      this.setEnabled(Boolean(myAccessRights && myAccessRights["write"]));
    },

    __buildLayout: function() {
      this.getChildControl("auto-recharge-title");
      this.getChildControl("auto-recharge-description");
      this.getChildControl("auto-recharge-options");
      this.getChildControl("auto-recharge-button");
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
