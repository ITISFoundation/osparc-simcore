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

    this._setLayout(new qx.ui.layout.VBox(15));

    this.__buildLayout();

    this.initTotalPrice();
    const creditPrice = osparc.store.Store.getInstance().getCreditPrice();
    if (creditPrice) {
      this.setCreditPrice(creditPrice);
    }
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
    "transactionCompleted": "qx.event.type.Event"
  },

  members: {
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
        case "amount-selector":
          control = this.__getAmountSelector();
          this._add(control);
          break;
        case "summary-view":
          control = this.__getSummaryView();
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
    },

    __buildLayout: function() {
      this.getChildControl("one-time-payment-title");
      this.getChildControl("one-time-payment-description");
      this.getChildControl("amount-selector");
      this.getChildControl("summary-view");
      this.getChildControl("buy-button");
    },

    __updateNCredits: function() {
      const totalPrice = this.getTotalPrice();
      const creditPrice = this.getCreditPrice();
      if (totalPrice !== null && creditPrice !== null) {
        this.setNCredits(totalPrice / creditPrice);
      }
    },

    __getAmountSelector: function() {
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
    }
  }
});
