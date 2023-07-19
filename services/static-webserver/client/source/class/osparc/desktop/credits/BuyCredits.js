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

    this._setLayout(new qx.ui.layout.VBox(20));

    this.__buildLayout();

    this.initNCredits();
    this.initCreditPrice();
  },

  properties: {
    nCredits: {
      check: "Number",
      init: 1,
      nullable: false,
      event: "changeNCredits",
      apply: "__applyNCredits"
    },

    creditPrice: {
      check: "Number",
      init: 5,
      nullable: false,
      event: "changeCreditPrice",
      apply: "__applyCreditPrice"
    },

    totalPrice: {
      check: "Number",
      init: null,
      nullable: false,
      event: "changeTotalPrice"
    }
  },

  events: {
    "transactionSuccessful": "qx.event.type.Data",
    "transactionFailed": "qx.event.type.Event"
  },

  members: {
    __creditPrice: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "credit-offers-view":
          control = this.__getCreditOffersView();
          this._add(control);
          break;
        case "credit-selector":
          control = this.__getCreditSelector();
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

    __buildLayout: function() {
      this.getChildControl("credit-offers-view");
      this.getChildControl("credit-selector");
      this.getChildControl("summary-view");
      this.getChildControl("buy-button");
    },

    __applyNCredits: function(nCredits) {
      let creditPrice = 5;
      if (nCredits >= 10) {
        creditPrice = 4;
      }
      if (nCredits >= 100) {
        creditPrice = 3;
      }
      if (nCredits >= 1000) {
        creditPrice = 2;
      }
      this.setCreditPrice(creditPrice);
      this.setTotalPrice(creditPrice * nCredits);
    },

    __applyCreditPrice: function(creditPrice) {
      this.setTotalPrice(creditPrice * this.getNCredits());
    },

    __getCreditOffersView: function() {
      const grid = new qx.ui.layout.Grid(15, 10);
      grid.setColumnAlign(0, "right", "middle");
      const layout = new qx.ui.container.Composite(grid);

      let row = 0;
      const creditsTitle = new qx.ui.basic.Label(this.tr("Credits")).set({
        font: "text-16"
      });
      layout.add(creditsTitle, {
        row,
        column: 0
      });

      const pricePerCreditTitle = new qx.ui.basic.Label(this.tr("Credit price")).set({
        font: "text-16"
      });
      layout.add(pricePerCreditTitle, {
        row,
        column: 1
      });
      row++;

      [
        [1, 5],
        [10, 4],
        [100, 3],
        [1000, 2]
      ].forEach(pair => {
        const creditsLabel = new qx.ui.basic.Label().set({
          value: pair[0].toString(),
          font: "text-14"
        });
        layout.add(creditsLabel, {
          row,
          column: 0
        });

        const pricePerCreditLabel = new qx.ui.basic.Label().set({
          value: pair[1] + " $",
          font: "text-14"
        });
        layout.add(pricePerCreditLabel, {
          row,
          column: 1
        });

        row++;
      });
      return layout;
    },

    __getCreditSelector: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(0));

      const minBtn = new qx.ui.form.Button().set({
        label: this.tr("-"),
        width: 25
      });
      minBtn.addListener("execute", () => this.setNCredits(this.getNCredits()-1));
      layout.add(minBtn);

      const nCreditsField = new qx.ui.form.TextField().set({
        width: 100,
        textAlign: "center",
        font: "text-14"
      });
      this.bind("nCredits", nCreditsField, "value", {
        converter: val => val.toString()
      });
      nCreditsField.addListener("changeValue", e => this.setNCredits(parseInt(e.getData())));
      layout.add(nCreditsField);

      const moreBtn = new qx.ui.form.Button().set({
        label: this.tr("+"),
        width: 25
      });
      moreBtn.addListener("execute", () => this.setNCredits(this.getNCredits()+1));
      layout.add(moreBtn);

      return layout;
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
        converter: totalPrice => totalPrice + " $"
      });
      layout.add(totalPriceLabel, {
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
        const oneCreditPrice = 5;
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

      const vatTitle = new qx.ui.basic.Label().set({
        value: "VAT 7%",
        font: "text-13"
      });
      layout.add(vatTitle, {
        row,
        column: 0
      });
      const vatLabel = new qx.ui.basic.Label().set({
        font: "text-13"
      });
      this.bind("totalPrice", vatLabel, "value", {
        converter: totalPrice => (totalPrice*0.07).toFixed(2) + " $"
      });
      layout.add(vatLabel, {
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
      buyBtn.addListener("execute", () => {
        buyBtn.setFetching(true);
        setTimeout(() => {
          buyBtn.setFetching(false);
          const nCredits = this.getNCredits();
          const totalPrice = this.getTotalPrice();
          const title = "3rd party payment gateway";
          const paymentGateway = new osparc.desktop.credits.PaymentGateway().set({
            url: "https://www.paymentservice.io?user_id=2&session_id=1234567890&token=5678",
            nCredits,
            totalPrice
          });
          const win = osparc.ui.window.Window.popUpInWindow(paymentGateway, title, 320, 445);
          win.center();
          win.open();
          paymentGateway.addListener("paymentSuccessful", () => {
            let msg = "Payment Successful";
            msg += "<br>";
            msg += "You now have " + nCredits + " more credits";
            osparc.component.message.FlashMessenger.getInstance().logAs(msg, "INFO");
            const store = osparc.store.Store.getInstance();
            store.setCredits(store.getCredits() + nCredits);
            this.fireDataEvent("transactionSuccessful", {
              nCredits,
              totalPrice
            });
          });
          paymentGateway.addListener("paymentFailed", () => {
            let msg = "Payment Failed";
            msg += "<br>";
            msg += "Please try again";
            osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
            this.fireEvent("transactionFailed");
          });
          paymentGateway.addListener("close", () => win.close());
        }, 1000);
      });
      return buyBtn;
    }
  }
});
