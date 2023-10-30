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

  events: {
    "addNewPaymentMethod": "qx.event.type.Event"
  },

  members: {
    __topUpAmountField: null,
    __monthlyLimitField: null,
    __paymentMethodField: null,
    __topUpAmountHelper: null,

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
      this.__topUpAmountField.setValue(arData["topUpAmountInUsd"]);
      this.__topUpAmountHelper.setValue(this.tr(`When your account reaches ${arData["minBalanceInUsd"]} credits, it gets recharged by this amount`));
      if (arData["monthlyLimitInUsd"]) {
        this.__monthlyLimitField.setValue(arData["monthlyLimitInUsd"] > 0 ? arData["monthlyLimitInUsd"] : 0);
      } else {
        this.__monthlyLimitField.setValue(arData["topUpCountdown"] > 0 ? arData["topUpCountdown"]*arData["topUpAmountInUsd"] : 0);
      }
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
      const autoRechargeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(15));

      const topUpAmountLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      const topUpAmountTitleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const topUpAmountTitle = new qx.ui.basic.Label().set({
        value: this.tr("RECHARGING AMOUNT (US$)"),
        font: "text-14"
      });
      topUpAmountTitleLayout.add(topUpAmountTitle);
      const topUpAmountInfo = new osparc.ui.hint.InfoHint("Amount in US$ payed when auto-recharge condition is satisfied.");
      topUpAmountTitleLayout.add(topUpAmountInfo);
      topUpAmountLayout.add(topUpAmountTitleLayout);
      const topUpAmountField = this.__topUpAmountField = new qx.ui.form.Spinner().set({
        minimum: 10,
        maximum: 10000,
        maxWidth: 200
      });
      topUpAmountLayout.add(topUpAmountField);
      const topUpAmountHelper = this.__topUpAmountHelper = new qx.ui.basic.Label().set({
        font: "text-12",
        rich: true,
        wrap: true
      });
      topUpAmountLayout.add(topUpAmountHelper);
      autoRechargeLayout.add(topUpAmountLayout);

      const monthlyLimitLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      const monthlyLimitTitleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const monthlyLimitTitle = new qx.ui.basic.Label().set({
        value: this.tr("MONTHLY LIMIT (US$)"),
        font: "text-14"
      });
      monthlyLimitTitleLayout.add(monthlyLimitTitle);
      const monthlyLimitTitleInfo = new osparc.ui.hint.InfoHint(this.tr("Maximum amount in US$ charged within a natural month."));
      monthlyLimitTitleLayout.add(monthlyLimitTitleInfo);
      monthlyLimitLayout.add(monthlyLimitTitleLayout);
      const monthlyLimitField = this.__monthlyLimitField = new qx.ui.form.Spinner().set({
        minimum: 0,
        maximum: 100000,
        maxWidth: 200
      });
      monthlyLimitLayout.add(monthlyLimitField);
      const monthlyLimitHelper = new qx.ui.basic.Label().set({
        value: this.tr("To disable spending limit, clear input field"),
        font: "text-12",
        rich: true,
        wrap: true
      });
      monthlyLimitLayout.add(monthlyLimitHelper);
      autoRechargeLayout.add(monthlyLimitLayout);

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
      const addNewPaymentMethod = new qx.ui.basic.Label(this.tr("Add Payment Method")).set({
        padding: 0,
        cursor: "pointer",
        font: "link-label-12"
      });
      addNewPaymentMethod.addListener("tap", () => this.fireEvent("addNewPaymentMethod"));
      paymentMethodLayout.add(addNewPaymentMethod);
      autoRechargeLayout.add(paymentMethodLayout);

      return autoRechargeLayout;
    },

    __getFieldsData: function() {
      return {
        minBalanceInUsd: 0,
        topUpAmountInUsd: this.__topUpAmountField.getValue(),
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
      const successfulMsg = this.tr("Auto recharge was successfully enabled. Coming soon.");
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
