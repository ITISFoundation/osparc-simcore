/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Ignacio Pascual

************************************************************************ */

qx.Class.define("osparc.desktop.credits.AutoRecharge", {
  extend: qx.ui.container.Stack,

  construct: function(walletId) {
    this.base(arguments);

    const store = osparc.store.Store.getInstance();
    const wallet = store.getWallets().find(w => w.getWalletId() == walletId);

    this.__buildLayout();
    this.setWallet(wallet);
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
    "addNewPaymentMethod": "qx.event.type.Event",
    "close": "qx.event.type.Event"
  },

  members: {
    __topUpAmountField: null,
    __monthlyLimitField: null,
    __paymentMethodField: null,

    __buildLayout: function() {
      this.removeAll();

      const titleText = this.tr("Auto-recharge");
      const introText = this.tr("Keep your balance running smoothly by automatically setting your credits to be recharged when it runs low.");

      this.__mainContent = new qx.ui.container.Composite(new qx.ui.layout.VBox(15).set({
        alignX: "center"
      }))
      const title = new qx.ui.basic.Label(titleText).set({
        marginTop: 25,
        font: "title-18"
      });
      const subtitle = new qx.ui.basic.Label(introText).set({
        rich: true,
        font: "text-14",
        textAlign: "center"
      });
      this.__mainContent.add(title);
      this.__mainContent.add(subtitle);
      this.__mainContent.add(this.__getAutoRechargeForm())
      this.__mainContent.add(this.__getButtons())
      this.add(this.__mainContent)

      this.__noPaymentMethodsContent = new qx.ui.container.Composite(new qx.ui.layout.VBox(15).set({
        alignX: "center"
      }))
      this.__noPaymentMethodsContent.add(new qx.ui.basic.Label(titleText).set({
        marginTop: 25,
        font: "title-18"
      }))
      this.__noPaymentMethodsContent.add(new qx.ui.basic.Label(introText).set({
        rich: true,
        font: "text-14",
        textAlign: "center"
      }))
      this.__noPaymentMethodsContent.add(new qx.ui.basic.Label(this.tr("Before the auto-recharge function can be activated you need to add your first payment method")).set({
        rich: true,
        font: "text-14",
        textAlign: "center"
      }))
      const addNewPaymentMethod = new qx.ui.basic.Label(this.tr("Add Payment Method")).set({
        cursor: "pointer",
        font: "link-label-14",
        textAlign: "center"
      });
      addNewPaymentMethod.addListener("tap", () => this.fireEvent("addNewPaymentMethod"));
      this.__noPaymentMethodsContent.add(addNewPaymentMethod)
      this.add(this.__noPaymentMethodsContent)

      this.__fetchingView = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
        alignX: "center",
        alignY: "middle"
      }))
      const image = new qx.ui.basic.Image("@FontAwesome5Solid/circle-notch/26")
      image.getContentElement().addClass("rotate")
      this.__fetchingView.add(image)
      this.add(this.__fetchingView)

      this.setSelection([this.__fetchingView])
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
      if (paymentMethodSB.getChildren().length) {
        this.setSelection([this.__fetchingView])
        // Get auto-recharge data
        const params = {
          url: {
            walletId: wallet.getWalletId()
          }
        };
        osparc.data.Resources.fetch("autoRecharge", "get", params)
          .then(arData => this.__populateForm(arData))
          .catch(err => console.error(err.message));
      } else {
        // Wallet has no payment methods
        this.setSelection([this.__noPaymentMethodsContent])
      }
    },

    __populateForm: function(arData) {
      this.__enabledField.setValue(arData.enabled);
      this.__topUpAmountField.setValue(arData["topUpAmountInUsd"]);
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
      this.setSelection([this.__mainContent])
    },

    __getAutoRechargeForm: function() {
      const autoRechargeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
        alignX: "center"
      })).set({
        marginTop: 20
      });

      const enabledLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        allowStretchX: false,
        width: 274
      });
      const enabledTitle = new qx.ui.basic.Label(this.tr("Enabled")).set({
        marginLeft: 2
      })
      const enabledCheckbox = this.__enabledField = new qx.ui.form.CheckBox().set({
        appearance: "appmotion-buy-credits-checkbox"
      });
      enabledLayout.add(enabledTitle);
      enabledLayout.add(enabledCheckbox);
      autoRechargeLayout.add(enabledLayout);

      const topUpAmountLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        allowStretchX: false,
        marginTop: 15
      });
      const topUpAmountTitleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const topUpAmountTitle = new qx.ui.basic.Label(this.tr("Recharging amount (USD)")).set({
        marginLeft: 15
      });
      topUpAmountTitleLayout.add(topUpAmountTitle);
      const topUpAmountInfo = new osparc.ui.hint.InfoHint("Amount in USD payed when auto-recharge condition is satisfied.");
      topUpAmountTitleLayout.add(topUpAmountInfo);
      topUpAmountLayout.add(topUpAmountTitleLayout);
      const topUpAmountField = this.__topUpAmountField = new qx.ui.form.Spinner().set({
        maximum: 10000,
        width: 300,
        appearance: "appmotion-buy-credits-spinner"
      });
      osparc.store.Store.getInstance().getMinimumAmount()
        .then(minimum => {
          topUpAmountInfo.setHintText(topUpAmountInfo.getText() + `. A minimum amount of ${minimum} USD is required.`);
          topUpAmountField.set({
            minimum
          });
        });
      topUpAmountLayout.add(topUpAmountField);
      autoRechargeLayout.add(topUpAmountLayout);

      const monthlyLimitLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        allowStretchX: false
      });
      const monthlyLimitTitleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const monthlyLimitTitle = new qx.ui.basic.Label(this.tr("Monthly limit (USD)")).set({
        marginLeft: 15
      });
      monthlyLimitTitleLayout.add(monthlyLimitTitle);
      const monthlyLimitTitleInfo = new osparc.ui.hint.InfoHint(this.tr("Maximum amount in USD charged within a natural month."));
      monthlyLimitTitleLayout.add(monthlyLimitTitleInfo);
      monthlyLimitLayout.add(monthlyLimitTitleLayout);
      const monthlyLimitField = this.__monthlyLimitField = new qx.ui.form.Spinner().set({
        minimum: 0,
        maximum: 100000,
        width: 300,
        appearance: "appmotion-buy-credits-spinner"
      });
      monthlyLimitLayout.add(monthlyLimitField);
      const monthlyLimitHelper = new qx.ui.basic.Label(this.tr("To disable spending limit, clear input field")).set({
        font: "text-12",
        marginLeft: 15,
        rich: true
      });
      monthlyLimitLayout.add(monthlyLimitHelper);
      autoRechargeLayout.add(monthlyLimitLayout);

      const paymentMethodLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        allowStretchX: false
      });
      const paymentMethodTitle = new qx.ui.basic.Label(this.tr("Pay with")).set({
        marginLeft: 15
      });
      paymentMethodLayout.add(paymentMethodTitle);
      const paymentMethodField = this.__paymentMethodField = new qx.ui.form.SelectBox().set({
        width: 300,
        appearance: "appmotion-buy-credits-select"
      });
      paymentMethodLayout.add(paymentMethodField);
      const addNewPaymentMethod = new qx.ui.basic.Label(this.tr("Add Payment Method")).set({
        marginLeft: 15,
        cursor: "pointer",
        font: "link-label-12"
      });
      addNewPaymentMethod.addListener("tap", () => this.fireEvent("addNewPaymentMethod"));
      paymentMethodLayout.add(addNewPaymentMethod);
      autoRechargeLayout.add(paymentMethodLayout);

      enabledCheckbox.bind("value", monthlyLimitField, "enabled")
      enabledCheckbox.bind("value", paymentMethodField, "enabled")
      enabledCheckbox.bind("value", topUpAmountField, "enabled")
      enabledCheckbox.bind("value", monthlyLimitHelper, "visibility", {
        converter: value => value ? "visible" : "hidden"
      })
      enabledCheckbox.bind("value", addNewPaymentMethod, "visibility", {
        converter: value => value ? "visible" : "hidden"
      })

      return autoRechargeLayout;
    },

    __getFieldsData: function() {
      return {
        topUpAmountInUsd: this.__topUpAmountField.getValue(),
        monthlyLimitInUsd: this.__monthlyLimitField.getValue(),
        paymentMethodId: this.__paymentMethodField.getSelection()[0].getModel(),
        enabled: this.__enabledField.getValue()
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
      params.data.enabled = enabled;
      osparc.data.Resources.fetch("autoRecharge", "put", params)
        .then(arData => {
          this.__populateForm(arData);
          wallet.setAutoRecharge(arData);
          osparc.FlashMessenger.logAs(successfulMsg, "INFO");
          this.fireEvent("close");
        })
        .finally(() => fetchButton.setFetching(false));
    },

    __getButtons: function() {
      const btnContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center"
      })).set({
        marginTop: 30,
        marginBottom: 15
      });
      const saveAutoRechargeBtn = new osparc.ui.form.FetchButton(this.tr("Save and close")).set({
        appearance: "appmotion-button-action"
      });
      const successfulMsg = this.tr("Changes on the Auto recharge were successfully saved");
      saveAutoRechargeBtn.addListener("execute", () => this.__updateAutoRecharge(this.__enabledField.getValue(), saveAutoRechargeBtn, successfulMsg));
      btnContainer.addAt(saveAutoRechargeBtn, 1)
      const cancelBtn = new qx.ui.form.Button("Cancel").set({
        appearance: "appmotion-button"
      });
      cancelBtn.addListener("execute", () => this.fireEvent("close"))
      btnContainer.addAt(cancelBtn, 0)
      return btnContainer;
    }
  }
});
