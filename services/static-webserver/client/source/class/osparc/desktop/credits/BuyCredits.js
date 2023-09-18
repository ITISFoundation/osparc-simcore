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

    this.initTotalPrice();
    this.initCreditPrice();
  },

  properties: {
    wallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: false,
      event: "changeWallet",
      apply: "__applyWallet"
    },

    totalPrice: {
      check: "Number",
      init: 50,
      nullable: false,
      event: "changeTotalPrice",
      apply: "__applyTotalPrice"
    },

    creditPrice: {
      check: "Number",
      init: 1,
      nullable: false,
      event: "changeCreditPrice",
      apply: "__applyCreditPrice"
    },

    nCredits: {
      check: "Number",
      init: null,
      nullable: false,
      event: "changeNCredits"
    }
  },

  events: {
    "transactionCompleted": "qx.event.type.Event"
  },

  statics: {
    CREDIT_PRICES: [
      [1, 1],
      [10, 1],
      [100, 1],
      [1000, 1]
    ]
  },

  members: {
    __creditPrice: null,

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
        case "one-time-payment-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(15));
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
        case "one-time-payment-title":
          control = new qx.ui.basic.Label().set({
            value: this.tr("One time payment:"),
            font: "text-16"
          });
          this.getChildControl("one-time-payment-layout").add(control);
          break;
        case "one-time-payment-description":
          control = new qx.ui.basic.Label().set({
            value: this.tr("A one-off, non-recurring payment."),
            font: "text-14",
            rich: true,
            wrap: true
          });
          this.getChildControl("one-time-payment-layout").add(control);
          break;
        case "credit-selector":
          control = this.__getCreditSelector();
          this.getChildControl("one-time-payment-layout").add(control);
          break;
        case "summary-view":
          control = this.__getSummaryView();
          this.getChildControl("one-time-payment-layout").add(control);
          break;
        case "buy-button":
          control = this.__getBuyButton();
          this.getChildControl("one-time-payment-layout").add(control);
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
      if (wallet) {
        const walletSelector = this.getChildControl("wallet-selector");
        walletSelector.getSelectables().forEach(selectable => {
          if (selectable.walletId === wallet.getWalletId()) {
            walletSelector.setSelection([selectable]);
          }
        });
      }
    },

    __buildLayout: function() {
      this.getChildControl("wallet-selector");
      this.getChildControl("credits-left-view");
      this.__buildOneTimePayment();

      this.getChildControl("credits-explanation");
      this.__buildAutoRecharge();
    },

    __buildOneTimePayment: function() {
      this.getChildControl("one-time-payment-title");
      this.getChildControl("one-time-payment-description");
      this.getChildControl("credit-selector");
      this.getChildControl("summary-view");
      this.getChildControl("buy-button");
    },

    __buildAutoRecharge: function() {
      this.getChildControl("auto-recharge-title");
      this.getChildControl("auto-recharge-description");
      this.getChildControl("auto-recharge-options");
      this.getChildControl("auto-recharge-button");
    },

    __applyTotalPrice: function(totalPrice) {
      let creditPrice = this.self().CREDIT_PRICES[0][1];

      if (totalPrice >= this.self().CREDIT_PRICES[1][0]) {
        creditPrice = this.self().CREDIT_PRICES[1][1];
      }
      if (totalPrice >= this.self().CREDIT_PRICES[2][0]) {
        creditPrice = this.self().CREDIT_PRICES[2][1];
      }
      if (totalPrice >= this.self().CREDIT_PRICES[3][0]) {
        creditPrice = this.self().CREDIT_PRICES[3][1];
      }
      this.setCreditPrice(creditPrice);
      this.setNCredits(totalPrice / creditPrice);
    },

    __applyCreditPrice: function(creditPrice) {
      this.setNCredits(creditPrice * this.getTotalPrice());
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
      const creditsLeftView = new osparc.desktop.credits.CreditsIndicatorWText();
      this.bind("wallet", creditsLeftView, "wallet");
      return creditsLeftView;
    },

    __getCreditSelector: function() {
      const vLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const label = new qx.ui.basic.Label().set({
        value: this.tr("Payment amount ($):"),
        font: "text-14"
      });
      vLayout.add(label);

      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(0));

      const lessBtn = new qx.ui.form.Button().set({
        label: this.tr("-"),
        width: 25
      });
      lessBtn.addListener("execute", () => this.setTotalPrice(this.getTotalPrice()-1));
      layout.add(lessBtn);

      const paymentAmountField = new qx.ui.form.TextField().set({
        width: 100,
        textAlign: "center",
        font: "text-14"
      });
      this.bind("totalPrice", paymentAmountField, "value", {
        converter: val => val.toString()
      });
      paymentAmountField.addListener("changeValue", e => this.setTotalPrice(Number(e.getData())));
      layout.add(paymentAmountField);

      const moreBtn = new qx.ui.form.Button().set({
        label: this.tr("+"),
        width: 25
      });
      moreBtn.addListener("execute", () => this.setTotalPrice(this.getTotalPrice()+1));
      layout.add(moreBtn);

      vLayout.add(layout);

      return vLayout;
    },

    __getSummaryView: function() {
      const grid = new qx.ui.layout.Grid(15, 10);
      grid.setColumnAlign(0, "right", "middle");
      const layout = new qx.ui.container.Composite(grid);

      let row = 0;
      const totalPriceTitle = new qx.ui.basic.Label().set({
        value: "Total price",
        font: "text-16"
      });
      layout.add(totalPriceTitle, {
        row,
        column: 0
      });
      const totalPriceLabel = new qx.ui.basic.Label().set({
        font: "text-16"
      });
      this.bind("totalPrice", totalPriceLabel, "value", {
        converter: totalPrice => (totalPrice ? totalPrice.toFixed(2) : 0).toString() + " $"
      });
      layout.add(totalPriceLabel, {
        row,
        column: 1
      });
      row++;

      const nCreditsTitle = new qx.ui.basic.Label().set({
        value: "Total credits",
        font: "text-16"
      });
      layout.add(nCreditsTitle, {
        row,
        column: 0
      });
      const nCreditsLabel = new qx.ui.basic.Label().set({
        font: "text-16"
      });
      this.bind("nCredits", nCreditsLabel, "value", {
        converter: nCredits => (nCredits ? nCredits.toFixed(2) : 0).toString()
      });
      layout.add(nCreditsLabel, {
        row,
        column: 1
      });
      row++;

      const creditPriceTitle = new qx.ui.basic.Label().set({
        value: "Credit price",
        font: "text-14"
      });
      layout.add(creditPriceTitle, {
        row,
        column: 0
      });
      const creditPriceLabel = new qx.ui.basic.Label().set({
        font: "text-14"
      });
      this.bind("creditPrice", creditPriceLabel, "value", {
        converter: nCredits => nCredits + " $"
      });
      layout.add(creditPriceLabel, {
        row,
        column: 1
      });
      row++;

      const savingTitle = new qx.ui.basic.Label().set({
        value: "Saving",
        font: "text-14"
      });
      layout.add(savingTitle, {
        row,
        column: 0
      });
      const savingLabel = new qx.ui.basic.Label("0 %").set({
        font: "text-14"
      });
      layout.add(savingLabel, {
        row,
        column: 1
      });
      this.addListener("changeTotalPrice", e => {
        const totalPrice = e.getData();
        const oneCreditPrice = this.self().CREDIT_PRICES[0][1];
        const saving = this.getNCredits()*oneCreditPrice - totalPrice;
        if (saving > 0) {
          savingLabel.set({
            value: "-" + saving.toFixed(2) + " $",
            textColor: "failed-red"
          });
        } else {
          savingLabel.set({
            value: "0 $",
            textColor: "text"
          });
        }
      });
      row++;

      const walletTitle = new qx.ui.basic.Label().set({
        value: "Credit Account",
        font: "text-14"
      });
      layout.add(walletTitle, {
        row,
        column: 0
      });
      const walletLabel = new qx.ui.basic.Label().set({
        font: "text-14"
      });
      this.bind("wallet", walletLabel, "value", {
        converter: wallet => wallet ? wallet.getName() : this.tr("Select Credit Account")
      });
      layout.add(walletLabel, {
        row,
        column: 1
      });
      row++;

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

      const buyingBtn = () => {
        buyBtn.set({
          fetching: true,
          label: this.tr("Buying...")
        });
      };
      const buyCreditsBtn = () => {
        buyBtn.set({
          fetching: false,
          label: this.tr("Buy Credits")
        });
      };
      buyBtn.addListener("execute", () => {
        const nCredits = this.getNCredits();
        const totalPrice = this.getTotalPrice();
        const wallet = this.getWallet();
        buyingBtn();

        const params = {
          url: {
            walletId: wallet.getWalletId()
          },
          data: {
            priceDollars: totalPrice,
            osparcCredits: nCredits
          }
        };
        osparc.data.Resources.fetch("payments", "startPayment", params)
          .then(data => {
            const paymentId = data["paymentId"];
            const url = data["paymentFormUrl"];
            const options = {
              width: 400,
              height: 400,
              top: 200,
              left: 100,
              scrollbars: false
            };
            const modal = true;
            const useNativeModalDialog = false; // this allow using the Blocker

            const blocker = qx.bom.Window.getBlocker();
            blocker.setBlockerColor("#FFF");
            blocker.setBlockerOpacity(0.6);
            let pgWindow = qx.bom.Window.open(
              url,
              "pgWindow",
              options,
              modal,
              useNativeModalDialog
            );

            // enhance the blocker
            const blockerDomEl = blocker.getBlockerElement();
            blockerDomEl.style.cursor = "pointer";

            // text on blocker
            const label = document.createElement("h1");
            label.innerHTML = "Don’t see the secure Payment Window?<br>Click here to complete your purchase";
            label.style.position = "fixed";
            const labelWidth = 550;
            const labelHeight = 100;
            label.style.width = labelWidth + "px";
            label.style.height = labelHeight + "px";
            const root = qx.core.Init.getApplication().getRoot();
            if (root && root.getBounds()) {
              label.style.left = Math.round(root.getBounds().width/2) - labelWidth/2 + "px";
              label.style.top = Math.round(root.getBounds().height/2) - labelHeight/2 + "px";
            }
            blockerDomEl.appendChild(label);

            blockerDomEl.addEventListener("click", () => pgWindow.focus());

            // Listen to socket event
            const socket = osparc.wrapper.WebSocket.getInstance();
            const slotName = "paymentCompleted";
            socket.on(slotName, jsonString => {
              const paymentData = JSON.parse(jsonString);
              if (paymentData["completedStatus"]) {
                const msg = this.tr("Payment ") + osparc.utils.Utils.onlyFirstsUp(paymentData["completedStatus"]);
                switch (paymentData["completedStatus"]) {
                  case "SUCCESS":
                    osparc.FlashMessenger.getInstance().logAs(msg, "INFO");
                    // demo purposes
                    wallet.setCreditsAvailable(wallet.getCreditsAvailable() + nCredits);
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
              socket.removeSlot(slotName);
              buyCreditsBtn();
              pgWindow.close();
              this.fireEvent("transactionCompleted");
            });

            const cancelPayment = () => {
              socket.removeSlot(slotName);
              buyCreditsBtn();
              // inform backend
              const params2 = {
                url: {
                  walletId: wallet.getWalletId(),
                  paymentId
                }
              };
              osparc.data.Resources.fetch("payments", "cancelPayment", params2);
            };
            // Listen to close window event
            pgWindow.onbeforeunload = () => {
              const msg = this.tr("The window was close. Try again and follow the instructions inside the opened window.");
              osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
              cancelPayment();
            };
          })
          .catch(err => {
            console.error(err);
            osparc.FlashMessenger.logAs(err.message, "ERROR");
            buyCreditsBtn();
          });
      });
      return buyBtn;
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
