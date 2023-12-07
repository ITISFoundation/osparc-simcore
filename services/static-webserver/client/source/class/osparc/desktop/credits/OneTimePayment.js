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

qx.Class.define("osparc.desktop.credits.OneTimePayment", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    this.__buildLayout();

    this.initTotalPrice();
    const store = osparc.store.Store.getInstance();
    store.bind("creditPrice", this, "creditPrice");
  },

  properties: {
    wallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: true,
      event: "changeWallet",
      apply: "__applyWallet"
    },

    totalPrice: {
      check: "Number",
      init: 50,
      nullable: false,
      event: "changeTotalPrice",
      apply: "__updateNCredits"
    },

    creditPrice: {
      check: "Number",
      init: null,
      nullable: false,
      event: "changeCreditPrice",
      apply: "__updateNCredits"
    },

    nCredits: {
      check: "Number",
      init: null,
      nullable: false,
      event: "changeNCredits"
    }
  },

  events: {
    "addNewPaymentMethod": "qx.event.type.Event",
    "transactionCompleted": "qx.event.type.Event"
  },

  members: {
    __paymentMethodSB: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "one-time-payment-title":
          control = new qx.ui.basic.Label().set({
            value: this.tr("One time payment:"),
            font: "text-16"
          });
          this._add(control);
          break;
        case "one-time-payment-description":
          control = new qx.ui.basic.Label().set({
            value: this.tr("A one-off, non-recurring payment."),
            font: "text-14",
            rich: true,
            wrap: true
          });
          this._add(control);
          break;
        case "summary-view":
          control = this.__getOneTimePaymentForm();
          this._add(control);
          break;
        case "payment-methods":
          control = this.__getPaymentMethods();
          this._add(control);
          break;
        case "buy-button":
          control = this.__getBuyButton();
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

      const paymentMethodSB = this.__paymentMethodSB;
      osparc.desktop.credits.Utils.populatePaymentMethodSelector(wallet, paymentMethodSB)
        .then(() => {
          const newItem = new qx.ui.form.ListItem("", null, null);
          paymentMethodSB.addAt(newItem, 0);
          paymentMethodSB.setSelection([newItem]);
        });
    },

    __buildLayout: function() {
      this.getChildControl("one-time-payment-title");
      this.getChildControl("one-time-payment-description");
      this.getChildControl("summary-view");
      this.getChildControl("payment-methods");
      this.getChildControl("buy-button");
    },

    __updateNCredits: function() {
      const totalPrice = this.getTotalPrice();
      const creditPrice = this.getCreditPrice();
      if (totalPrice !== null && creditPrice !== null) {
        this.setNCredits(totalPrice / creditPrice);
      }
    },

    __getOneTimePaymentForm: function() {
      const grid = new qx.ui.layout.Grid(25, 5);
      grid.setColumnAlign(0, "center", "middle");
      grid.setColumnAlign(1, "center", "middle");
      grid.setColumnAlign(2, "center", "middle");
      const layout = new qx.ui.container.Composite(grid);

      let row = 0;
      const totalTitle = new qx.ui.basic.Label().set({
        value: this.tr("TOTAL (US$)"),
        font: "text-14"
      });
      layout.add(totalTitle, {
        row,
        column: 0
      });
      const nCreditsTitle = new qx.ui.basic.Label().set({
        value: this.tr("CREDITS"),
        font: "text-14"
      });
      layout.add(nCreditsTitle, {
        row,
        column: 1
      });
      const creditPriceTitle = new qx.ui.basic.Label().set({
        value: this.tr("CREDIT PRICE"),
        font: "text-14"
      });
      layout.add(creditPriceTitle, {
        row,
        column: 2
      });
      row++;

      const paymentTotalField = new qx.ui.form.Spinner().set({
        width: 80,
        font: "text-14",
        minimum: 10,
        maximum: 10000,
        singleStep: 10
      });
      this.bind("totalPrice", paymentTotalField, "value");
      paymentTotalField.addListener("changeValue", e => this.setTotalPrice(e.getData()));
      layout.add(paymentTotalField, {
        row,
        column: 0
      });

      const nCreditsLabel = new qx.ui.basic.Label().set({
        font: "text-14"
      });
      this.bind("nCredits", nCreditsLabel, "value", {
        converter: nCredits => (nCredits ? nCredits.toFixed(2) : 0).toString()
      });
      layout.add(nCreditsLabel, {
        row,
        column: 1
      });

      const creditPriceLabel = new qx.ui.basic.Label().set({
        font: "text-14"
      });
      this.bind("creditPrice", creditPriceLabel, "value", {
        converter: nCredits => nCredits + " US$"
      });
      layout.add(creditPriceLabel, {
        row,
        column: 2
      });

      row++;

      return layout;
    },

    __getPaymentMethods: function() {
      const grid = new qx.ui.layout.Grid(25, 5);
      const layout = new qx.ui.container.Composite(grid);

      const title = new qx.ui.basic.Label().set({
        value: this.tr("PAY WITH"),
        font: "text-14"
      });
      layout.add(title, {
        row: 0,
        column: 0
      });

      const paymentMethodSB = this.__paymentMethodSB = new qx.ui.form.SelectBox().set({
        minWidth: 200,
        maxWidth: 200
      });
      layout.add(paymentMethodSB, {
        row: 1,
        column: 0
      });

      const addNewPaymentMethod = new qx.ui.basic.Label(this.tr("Add Payment Method")).set({
        padding: 0,
        cursor: "pointer",
        font: "link-label-12"
      });
      addNewPaymentMethod.addListener("tap", () => this.fireEvent("addNewPaymentMethod"));
      layout.add(addNewPaymentMethod, {
        row: 2,
        column: 0
      });

      return layout;
    },

    __getBuyButton: function() {
      const buyBtn = new osparc.ui.form.FetchButton().set({
        label: this.tr("Buy credits"),
        font: "text-16",
        appearance: "strong-button",
        maxWidth: 150,
        center: true
      });
      buyBtn.addListener("execute", () => this.__startPayment());
      return buyBtn;
    },

    __setBuyBtnFetching: function(isBuying) {
      const buyBtn = this.getChildControl("buy-button");
      buyBtn.set({
        fetching: isBuying,
        label: isBuying ? this.tr("Buying...") : this.tr("Buy Credits")
      });
    },

    __paymentCompleted: function(paymentData) {
      this.__setBuyBtnFetching(false);

      if (paymentData["completedStatus"]) {
        const msg = this.tr("Payment ") + osparc.utils.Utils.onlyFirstsUp(paymentData["completedStatus"]);
        switch (paymentData["completedStatus"]) {
          case "SUCCESS":
            osparc.FlashMessenger.getInstance().logAs(msg, "INFO");
            break;
          case "PENDING":
            osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
            break;
          case "CANCELED":
          case "FAILED":
            osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
            break;
          default:
            console.error("completedStatus unknown");
            break;
        }
      }
      this.fireEvent("transactionCompleted");
    },

    __cancelPayment: function(paymentId) {
      this.__setBuyBtnFetching(false);

      const wallet = this.getWallet();
      // inform backend
      const params = {
        url: {
          walletId: wallet.getWalletId(),
          paymentId
        }
      };
      osparc.data.Resources.fetch("payments", "cancelPayment", params);
    },

    __windowClosed: function(paymentId) {
      const msg = this.tr("The window was closed. Try again and follow the instructions inside the opened window.");
      osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
      this.__cancelPayment(paymentId);
    },

    __startPayment: function() {
      this.__setBuyBtnFetching(true);

      const wallet = this.getWallet();
      const nCredits = this.getNCredits();
      const totalPrice = this.getTotalPrice();
      const params = {
        url: {
          walletId: wallet.getWalletId()
        },
        data: {
          priceDollars: totalPrice,
          osparcCredits: nCredits
        }
      };
      const paymentMethodId = this.__paymentMethodSB.getSelection()[0].getModel();
      if (paymentMethodId) {
        params.url["paymentMethodId"] = paymentMethodId;
        osparc.data.Resources.fetch("payments", "payWithPaymentMethod", params)
          .then(() => {
            // Listen to socket event
            const socket = osparc.wrapper.WebSocket.getInstance();
            const slotName = "paymentCompleted";
            socket.on(slotName, jsonString => {
              const paymentData = JSON.parse(jsonString);
              this.__paymentCompleted(paymentData);
              socket.removeSlot(slotName);
            });
          })
          .catch(err => {
            console.error(err);
            osparc.FlashMessenger.logAs(err.message, "ERROR");
          })
          .finally(() => this.__setBuyBtnFetching(false));
      } else {
        osparc.data.Resources.fetch("payments", "startPayment", params)
          .then(data => {
            const paymentId = data["paymentId"];
            const url = data["paymentFormUrl"];
            const pgWindow = this.__popUpPaymentGateway(paymentId, url);

            // Listen to socket event
            const socket = osparc.wrapper.WebSocket.getInstance();
            const slotName = "paymentCompleted";
            socket.on(slotName, jsonString => {
              const paymentData = JSON.parse(jsonString);
              this.__paymentCompleted(paymentData);
              socket.removeSlot(slotName);
              pgWindow.close();
            });
          })
          .catch(err => {
            console.error(err);
            osparc.FlashMessenger.logAs(err.message, "ERROR");
          })
          .finally(() => this.__setBuyBtnFetching(false));
      }
    },

    __popUpPaymentGateway: function(paymentId, url) {
      const options = {
        width: 450,
        height: 600
      };

      const pgWindow = osparc.desktop.credits.PaymentGatewayWindow.popUp(
        url,
        "Buy Credits",
        options
      );
      // listen to "tap" instead of "execute": the "execute" is not propagated
      pgWindow.getChildControl("close-button").addListener("tap", () => this.__windowClosed(paymentId));

      return pgWindow;
    },

    __popUpPaymentGatewayOld: function(paymentId, url) {
      const options = {
        width: 450,
        height: 600,
        top: 100,
        left: 200,
        scrollbars: false
      };
      const modal = true;
      const useNativeModalDialog = false; // this allow using the Blocker

      const pgWindow = osparc.desktop.credits.PaymentGatewayWindow.popUpOld(
        url,
        "pgWindow",
        options,
        modal,
        useNativeModalDialog
      );

      // Listen to close window event (Bug: it doesn't work)
      pgWindow.onbeforeunload = () => this.__windowClosed(paymentId);

      return pgWindow;
    }
  }
});
