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
    __lowerThreshold: null,
    __paymentAmount: null,
    __nTopUps: null,
    __paymentMethod: null,

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
        case "auto-recharge-form":
          control = this.__getAutoRechargeOptions();
          this._add(control);
          break;
        case "enable-auto-recharge-button":
          control = this.__getEnableAutoRechargeButton();
          this._add(control);
          break;
        case "save-auto-recharge-button":
          control = this.__getSaveAutoRechargeButton();
          control.exclude();
          this._add(control);
          break;
        case "disable-auto-recharge-button":
          control = this.__getDisableAutoRechargeButton();
          control.exclude();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyWallet: function(wallet) {
      let myAccessRights = null;
      if (wallet) {
        myAccessRights = wallet.getMyAccessRights();
        if (myAccessRights["write"]) {
          const params = {
            url: {
              walletId: wallet.getWalletId()
            }
          };
          osparc.data.Resources.fetch("auto-recharge", "get", params)
            .then(data => {
              console.log("auto-recharge", data);
              /*
              this.__lowerThreshold.setValue();
              this.__paymentAmount.setValue();
              this.__paymentMethod.setValue();
              */
              this.getChildControl("enable-auto-recharge-button");
              this.getChildControl("save-auto-recharge-button");
              this.getChildControl("disable-auto-recharge-button");
            })
            .catch(err => console.error(err.message));
        }
      }
      this.setEnabled(Boolean(myAccessRights && myAccessRights["write"]));
    },

    __buildLayout: function() {
      this.getChildControl("auto-recharge-title");
      this.getChildControl("auto-recharge-description");
      this.getChildControl("auto-recharge-form");
      this.getChildControl("enable-auto-recharge-button");
      this.getChildControl("save-auto-recharge-button");
      this.getChildControl("disable-auto-recharge-button");
    },

    __getAutoRechargeOptions: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const lowerThresholdLabel = new qx.ui.basic.Label().set({
        value: this.tr("When balance goes below ($):"),
        font: "text-14"
      });
      layout.add(lowerThresholdLabel);

      const lowerThresholdField = this.__lowerThreshold = new qx.ui.form.TextField().set({
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

      const paymentAmountField = this.__paymentAmount = new qx.ui.form.TextField().set({
        maxWidth: 100,
        textAlign: "center",
        font: "text-14"
      });
      layout.add(paymentAmountField);

      const nTopUpsLabel = new qx.ui.basic.Label().set({
        value: this.tr("Number of Top ups:"),
        font: "text-14"
      });
      layout.add(nTopUpsLabel);

      const nTopUpsField = this.__nTopUps = new qx.ui.form.Spinner().set({
        minimum: 0,
        maximum: 10000,
        maxWidth: 100
      });
      layout.add(nTopUpsField);

      const label = new qx.ui.basic.Label().set({
        value: this.tr("Payment Method:"),
        font: "text-14"
      });
      layout.add(label);

      const paymentMethods = this.__paymentMethod = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      layout.add(paymentMethods);

      return layout;
    },

    __getEnableAutoRechargeButton: function() {
      const enableAutoRechargeBtn = new osparc.ui.form.FetchButton().set({
        label: this.tr("Enable Auto Recharge"),
        font: "text-16",
        appearance: "strong-button",
        maxWidth: 200,
        center: true
      });
      enableAutoRechargeBtn.addListener("execute", () => {
        enableAutoRechargeBtn.setFetching(true);
      });
      return enableAutoRechargeBtn;
    },

    __getSaveAutoRechargeButton: function() {
      const saveAutoRechargeBtn = new osparc.ui.form.FetchButton().set({
        label: this.tr("Save changes"),
        font: "text-16",
        appearance: "strong-button",
        maxWidth: 200,
        center: true
      });
      return saveAutoRechargeBtn;
    },

    __getDisableAutoRechargeButton: function() {
      const disableAutoRechargeBtn = new osparc.ui.form.FetchButton().set({
        label: this.tr("Disable Auto Recharge"),
        font: "text-16",
        appearance: "danger-button",
        maxWidth: 200,
        center: true
      });
      return disableAutoRechargeBtn;
    }
  }
});
