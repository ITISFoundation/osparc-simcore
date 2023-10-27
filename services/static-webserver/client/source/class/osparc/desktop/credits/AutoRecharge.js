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
    __rechargeField: null,
    __limitField: null,
    __paymentMethodField: null,

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

    __requestData: async function() {
      const wallet = this.getWallet();
      const paymentMethodSB = this.__paymentMethodField;
      await osparc.desktop.credits.Utils.populatePaymentMethodSelector(wallet, paymentMethodSB);

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
      this.__rechargeField.setValue(arData["topUpAmountInUsd"]);
      this.__limitField.setValue(arData["topUpCountdown"] > 0 ? arData["topUpCountdown"]*arData["topUpAmountInUsd"] : 0);
      const paymentMethodSB = this.__paymentMethodField;
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
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(15));

      const rechargeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      const rechargeTitle = new qx.ui.basic.Label().set({
        value: this.tr("RECHARGING AMOUNT (US$)"),
        font: "text-14"
      });
      rechargeLayout.add(rechargeTitle);
      const rechargeField = this.__rechargeField = new qx.ui.form.Spinner().set({
        minimum: 10,
        maximum: 10000,
        maxWidth: 200
      });
      rechargeLayout.add(rechargeField);
      const rechargeHelper = new qx.ui.basic.Label().set({
        value: this.tr("When your account reaches 25, it gets recharged by this amount"),
        font: "text-12",
        rich: true,
        wrap: true
      });
      rechargeLayout.add(rechargeHelper);
      layout.add(rechargeLayout);

      const limitLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      const limitTitle = new qx.ui.basic.Label().set({
        value: this.tr("MONTHLY LIMIT (US$)"),
        font: "text-14"
      });
      limitLayout.add(limitTitle);
      const limitField = this.__limitField = new qx.ui.form.Spinner().set({
        minimum: 100,
        maximum: 100000,
        maxWidth: 200
      });
      limitLayout.add(limitField);
      const limitHelper = new qx.ui.basic.Label().set({
        value: this.tr("To disable spending limit, clear input field"),
        font: "text-12",
        rich: true,
        wrap: true
      });
      limitLayout.add(limitHelper);
      layout.add(limitLayout);

      const paymentMethodLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      const paymentMethodTitle = new qx.ui.basic.Label().set({
        value: this.tr("PAY WITH"),
        font: "text-14"
      });
      paymentMethodLayout.add(paymentMethodTitle);
      const paymentMethodField = this.__paymentMethodField = new qx.ui.form.SelectBox().set({
        minWidth: 200,
        maxWidth: 200
      });
      paymentMethodLayout.add(paymentMethodField);
      layout.add(paymentMethodLayout);

      return layout;
    },

    __getFieldsData: function() {
      return {
        minBalanceInUsd: 0,
        topUpAmountInUsd: this.__rechargeField.getValue(),
        topUpCountdown: 30,
        paymentMethodId: this.__paymentMethodField.getSelection()[0].getModel()
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
