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
    __form: null,

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
          control = this.__getAutoRechargeForm();
          this._add(control);
          break;
        case "enable-auto-recharge-button":
          control = this.__getEnableAutoRechargeButton();
          this._add(control);
          break;
        case "buttons-layout-2":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._add(control);
          break;
        case "save-auto-recharge-button":
          control = this.__getSaveAutoRechargeButton();
          control.exclude();
          this.getChildControl("buttons-layout-2").add(control);
          break;
        case "disable-auto-recharge-button":
          control = this.__getDisableAutoRechargeButton();
          control.exclude();
          this.getChildControl("buttons-layout-2").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("auto-recharge-title");
      this.getChildControl("auto-recharge-description");
      this.getChildControl("auto-recharge-form");
      this.getChildControl("enable-auto-recharge-button");
      this.getChildControl("save-auto-recharge-button");
      this.getChildControl("disable-auto-recharge-button");
    },

    __applyWallet: function(wallet) {
      let myAccessRights = null;
      if (wallet) {
        myAccessRights = wallet.getMyAccessRights();
        if (myAccessRights["write"]) {
          this.__requestData();
        }
      }
      this.setEnabled(Boolean(myAccessRights && myAccessRights["write"]));
    },

    __requestData: function() {
      const wallet = this.getWallet();
      // populate the payment methods
      osparc.desktop.credits.Utils.getPaymentMethods(wallet.getWalletId())
        .then(paymentMethods => {
          const paymentMethodSB = this.__form.getItem("paymentMethod");
          paymentMethodSB.removeAll();
          paymentMethods.forEach(paymentMethod => {
            let label = paymentMethod.cardHolderName;
            label += " ";
            label += paymentMethod.cardNumberMasked.substr(paymentMethod.cardNumberMasked.length - 9);
            const lItem = new qx.ui.form.ListItem(label, null, paymentMethod.idr);
            paymentMethodSB.add(lItem);
          });
        });

      // populate the form
      const params = {
        url: {
          walletId: wallet.getWalletId()
        }
      };
      osparc.data.Resources.fetch("autoRecharge", "get", params)
        .then(arData => this.__populateForm(arData))
        .catch(err => console.error(err.message));
    },

    __populateForm: function(arData) {
      this.__form.getItem("minBalanceInUsd").setValue(arData["minBalanceInUsd"]);
      this.__form.getItem("topUpAmountInUsd").setValue(arData["topUpAmountInUsd"]);
      this.__form.getItem("topUpCountdown").setValue(arData["topUpCountdown"] ? arData["topUpCountdown"] : -1);
      const paymentMethodSB = this.__form.getItem("paymentMethod");
      const paymentMethodFound = paymentMethodSB.getSelectables().find(selectable => selectable.getModel() === arData["paymentMethodId"]);
      if (paymentMethodFound) {
        paymentMethodSB.setSelection([paymentMethodFound]);
      }

      if (arData["enabled"]) {
        this.getChildControl("enable-auto-recharge-button").exclude();
        this.getChildControl("save-auto-recharge-button").show();
        this.getChildControl("disable-auto-recharge-button").show();
      } else {
        this.getChildControl("enable-auto-recharge-button").show();
        this.getChildControl("save-auto-recharge-button").exclude();
        this.getChildControl("disable-auto-recharge-button").exclude();
      }
    },

    __getAutoRechargeForm: function() {
      const form = this.__form = new qx.ui.form.Form();

      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const lowerThresholdLabel = new qx.ui.basic.Label().set({
        value: this.tr("When balance goes below (US$):"),
        font: "text-14"
      });
      layout.add(lowerThresholdLabel);

      const lowerThresholdField = new qx.ui.form.Spinner().set({
        minimum: 0,
        maximum: 10000,
        maxWidth: 200
      });
      form.add(lowerThresholdField, null, null, "minBalanceInUsd");
      layout.add(lowerThresholdField);

      const balanceBackLabel = new qx.ui.basic.Label().set({
        value: this.tr("Top up with (US$):"),
        font: "text-14"
      });
      layout.add(balanceBackLabel);

      const paymentAmountField = new qx.ui.form.Spinner().set({
        minimum: 0,
        maximum: 10000,
        maxWidth: 200
      });
      form.add(paymentAmountField, null, null, "topUpAmountInUsd");
      layout.add(paymentAmountField);

      const nTopUpsLabel = new qx.ui.basic.Label().set({
        value: this.tr("Number of Top ups left (-1 unlimited):"),
        font: "text-14"
      });
      layout.add(nTopUpsLabel);

      const nTopUpsField = new qx.ui.form.Spinner().set({
        minimum: -1,
        maximum: 100,
        maxWidth: 200
      });
      form.add(nTopUpsField, null, null, "topUpCountdown");
      layout.add(nTopUpsField);

      const label = new qx.ui.basic.Label().set({
        value: this.tr("Payment Method:"),
        font: "text-14"
      });
      layout.add(label);

      const paymentMethods = new qx.ui.form.SelectBox().set({
        maxWidth: 200
      });
      form.add(paymentMethods, null, null, "paymentMethod");
      layout.add(paymentMethods);

      return layout;
    },

    __getFieldsData: function() {
      return {
        minBalanceInUsd: this.__form.getItem("minBalanceInUsd").getValue(),
        topUpAmountInUsd: this.__form.getItem("topUpAmountInUsd").getValue(),
        topUpCountdown: this.__form.getItem("topUpCountdown").getValue(),
        paymentMethodId: this.__form.getItem("paymentMethod").getSelection()[0].getModel()
      };
    },

    __updateAutoRecharge: function(enabled, fetchButton, successfulMsg) {
      const wallet = this.getWallet();
      fetchButton.setFetching(true);
      const params = {
        url: {
          walletId: wallet.getWalletId()
        },
        data: this.__getFieldsData()
      };
      params.data["enabled"] = enabled;
      osparc.data.Resources.fetch("autoRecharge", "put", params)
        .then(arData => {
          this.__populateForm(arData);
          wallet.setAutoRecharge(arData);
          osparc.FlashMessenger.getInstance().logAs(successfulMsg, "INFO");
        })
        .finally(() => fetchButton.setFetching(false));
    },

    __getEnableAutoRechargeButton: function() {
      const enableAutoRechargeBtn = new osparc.ui.form.FetchButton().set({
        label: this.tr("Enable"),
        font: "text-14",
        appearance: "strong-button",
        maxWidth: 200,
        center: true
      });
      const successfulMsg = this.tr("Auto recharge was successfully enabled");
      enableAutoRechargeBtn.addListener("execute", () => this.__updateAutoRecharge(true, enableAutoRechargeBtn, successfulMsg));
      return enableAutoRechargeBtn;
    },

    __getSaveAutoRechargeButton: function() {
      const saveAutoRechargeBtn = new osparc.ui.form.FetchButton().set({
        label: this.tr("Save changes"),
        font: "text-14",
        appearance: "strong-button",
        maxWidth: 200,
        center: true
      });
      const successfulMsg = this.tr("Changes on the Auto recharge were successfully saved");
      saveAutoRechargeBtn.addListener("execute", () => this.__updateAutoRecharge(true, saveAutoRechargeBtn, successfulMsg));
      return saveAutoRechargeBtn;
    },

    __getDisableAutoRechargeButton: function() {
      const disableAutoRechargeBtn = new osparc.ui.form.FetchButton().set({
        label: this.tr("Disable"),
        font: "text-14",
        appearance: "danger-button",
        maxWidth: 200,
        center: true
      });
      const successfulMsg = this.tr("Auto recharge was successfully disabled");
      disableAutoRechargeBtn.addListener("execute", () => this.__updateAutoRecharge(false, disableAutoRechargeBtn, successfulMsg));
      return disableAutoRechargeBtn;
    }
  }
});
