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

    __applyWallet: function(wallet) {
      let myAccessRights = null;
      if (wallet) {
        myAccessRights = wallet.getMyAccessRights();
        if (myAccessRights["write"]) {
          this.__populateForms();
        }
      }
      this.setEnabled(Boolean(myAccessRights && myAccessRights["write"]));
    },

    __populateForms: function() {
      const wallet = this.getWallet();
      // populate the payment methods
      osparc.desktop.credits.Utils.getPaymentMethods(wallet.getWalletId())
        .then(paymentMethods => {
          this.__paymentMethod.removeAll();
          paymentMethods.forEach(paymentMethod => {
            let label = paymentMethod.cardHolderName;
            label += " ";
            label += paymentMethod.cardNumberMasked.substr(paymentMethod.cardNumberMasked.length - 9);
            const lItem = new qx.ui.form.ListItem(label, null, paymentMethod.idr);
            this.__paymentMethod.add(lItem);
          });
        });

      // populate the form
      const params = {
        url: {
          walletId: wallet.getWalletId()
        }
      };
      osparc.data.Resources.fetch("auto-recharge", "get", params)
        .then(data => {
          this.__lowerThreshold.setValue(data["minBalanceInUsd"]);
          this.__paymentAmount.setValue(data["topUpAmountInUsd"]);
          this.__nTopUps.setValue(data["topUpCountdown"] ? data["topUpCountdown"] : -1);
          osparc.desktop.credits.Utils.getPaymentMethod(data["paymentMethodId"])
            .then(paymentMethod => {
              if (paymentMethod) {
                console.log("paymentMethod", paymentMethod);
                this.__paymentMethod.getSelectables().forEach(selectable => {
                  console.log("selectable", selectable);
                });
              }
            });

          if (data["enabled"]) {
            this.getChildControl("enable-auto-recharge-button").exclude();
            this.getChildControl("save-auto-recharge-button").show();
            this.getChildControl("disable-auto-recharge-button").show();
          } else {
            this.getChildControl("enable-auto-recharge-button").show();
            this.getChildControl("save-auto-recharge-button").exclude();
            this.getChildControl("disable-auto-recharge-button").exclude();
          }
        })
        .catch(err => console.error(err.message));
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

      const lowerThresholdField = this.__lowerThreshold = new qx.ui.form.Spinner().set({
        minimum: 0,
        maximum: 10000,
        maxWidth: 200
      });
      layout.add(lowerThresholdField);

      const balanceBackLabel = new qx.ui.basic.Label().set({
        value: this.tr("Top up with ($):"),
        font: "text-14"
      });
      layout.add(balanceBackLabel);

      const paymentAmountField = this.__paymentAmount = new qx.ui.form.Spinner().set({
        minimum: 0,
        maximum: 10000,
        maxWidth: 200
      });
      layout.add(paymentAmountField);

      const nTopUpsLabel = new qx.ui.basic.Label().set({
        value: this.tr("Number of Top ups left (-1 unlimited):"),
        font: "text-14"
      });
      layout.add(nTopUpsLabel);

      const nTopUpsField = this.__nTopUps = new qx.ui.form.Spinner().set({
        minimum: -1,
        maximum: 100,
        maxWidth: 200
      });
      layout.add(nTopUpsField);

      const label = new qx.ui.basic.Label().set({
        value: this.tr("Payment Method:"),
        font: "text-14"
      });
      layout.add(label);

      const paymentMethods = this.__paymentMethod = new qx.ui.form.SelectBox().set({
        maxWidth: 200
      });
      layout.add(paymentMethods);

      return layout;
    },

    __getFieldsData: function() {
      return {
        minBalanceInUsd: this.__lowerThreshold.getValue(),
        topUpAmountInUsd: this.__paymentAmount.getValue(),
        topUpCountdown: this.__nTopUps.getValue(),
        paymentMethodId: this.__paymentMethod.getSelection()[0].getModel()
      };
    },

    __getEnableAutoRechargeButton: function() {
      const enableAutoRechargeBtn = new osparc.ui.form.FetchButton().set({
        label: this.tr("Enable"),
        font: "text-16",
        appearance: "strong-button",
        maxWidth: 200,
        center: true
      });
      enableAutoRechargeBtn.addListener("execute", () => {
        enableAutoRechargeBtn.setFetching(true);
        const params = {
          url: {
            walletId: this.getWallet().getWalletId()
          },
          data: this.__getFieldsData()
        };
        params.data["enabled"] = true;
        osparc.data.Resources.fetch("auto-recharge", "put", params)
          .then(() => {
            this.__populateForms();
          })
          .finally(() => enableAutoRechargeBtn.setFetching(false));
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
        label: this.tr("Disable"),
        font: "text-16",
        appearance: "danger-button",
        maxWidth: 200,
        center: true
      });
      disableAutoRechargeBtn.addListener("execute", () => {
        disableAutoRechargeBtn.setFetching(true);
        const params = {
          url: {
            walletId: this.getWallet().getWalletId()
          },
          data: this.__getFieldsData()
        };
        params.data["enabled"] = false;
        osparc.data.Resources.fetch("auto-recharge", "put", params)
          .then(() => {
            this.__populateForms();
          })
          .finally(() => disableAutoRechargeBtn.setFetching(false));
      });
      return disableAutoRechargeBtn;
    }
  }
});
