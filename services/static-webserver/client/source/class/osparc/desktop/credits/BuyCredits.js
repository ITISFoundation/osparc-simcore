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

    this._setLayout(new qx.ui.layout.HBox(80));

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
    "transactionSuccessful": "qx.event.type.Data"
  },

  statics: {
    CREDIT_PRICES: [
      [1, 3],
      [10, 2.5],
      [100, 2],
      [1000, 1.5]
    ]
  },

  members: {
    __creditPrice: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "left-side":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(20));
          this._add(control);
          break;
        case "right-side":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(20));
          this._add(control, {
            flex: 1
          });
          break;
        case "credits-left-view":
          control = this.__getCreditsLeftView();
          this.getChildControl("left-side").add(control);
          break;
        case "credit-offers-view":
          control = this.__getCreditOffersView();
          this.getChildControl("left-side").add(control);
          break;
        case "credit-selector":
          control = this.__getCreditSelector();
          this.getChildControl("left-side").add(control);
          break;
        case "summary-view":
          control = this.__getSummaryView();
          this.getChildControl("left-side").add(control);
          break;
        case "buy-button":
          control = this.__getBuyButton();
          this.getChildControl("left-side").add(control);
          break;
        case "credits-explanation":
          control = this.__getCreditsExplanation();
          this.getChildControl("right-side").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("credits-left-view");
      this.getChildControl("credit-offers-view");
      this.getChildControl("credit-selector");
      this.getChildControl("summary-view");
      this.getChildControl("buy-button");

      this.getChildControl("credits-explanation");
    },

    __applyNCredits: function(nCredits) {
      let creditPrice = this.self().CREDIT_PRICES[0][1];

      if (nCredits >= this.self().CREDIT_PRICES[1][0]) {
        creditPrice = this.self().CREDIT_PRICES[1][1];
      }
      if (nCredits >= this.self().CREDIT_PRICES[2][0]) {
        creditPrice = this.self().CREDIT_PRICES[2][1];
      }
      if (nCredits >= this.self().CREDIT_PRICES[3][0]) {
        creditPrice = this.self().CREDIT_PRICES[3][1];
      }
      this.setCreditPrice(creditPrice);
      this.setTotalPrice(creditPrice * nCredits);
    },

    __applyCreditPrice: function(creditPrice) {
      this.setTotalPrice(creditPrice * this.getNCredits());
    },

    __getCreditsLeftView: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      const creditsLabel = new qx.ui.basic.Label().set({
        font: "text-14"
      });
      const store = osparc.store.Store.getInstance();
      const currentWallet = store.getCurrentWallet();
      currentWallet.bind("credits", creditsLabel, "value", {
        converter: val => "You have " + val + " credits left"
      });
      layout.add(creditsLabel);

      const progressBar = new osparc.desktop.credits.CreditsIndicator(currentWallet);
      layout.add(progressBar);

      return layout;
    },

    __getCreditOffersView: function() {
      const grid = new qx.ui.layout.Grid(15, 10);
      grid.setColumnAlign(0, "right", "middle");
      const layout = new qx.ui.container.Composite(grid).set({
        padding: 5,
        backgroundColor: "background-main-3"
      });

      let row = 0;
      const creditsTitle = new qx.ui.basic.Label(this.tr("Credits")).set({
        font: "text-16"
      });
      layout.add(creditsTitle, {
        row,
        column: 0
      });

      const pricePerCreditTitle = new qx.ui.basic.Label(this.tr("Price/Credit")).set({
        font: "text-16"
      });
      layout.add(pricePerCreditTitle, {
        row,
        column: 1
      });
      row++;

      this.self().CREDIT_PRICES.forEach(pair => {
        const creditsLabel = new qx.ui.basic.Label().set({
          value: "> " + pair[0],
          font: "text-14"
        });
        layout.add(creditsLabel, {
          row,
          column: 0
        });

        const pricePerCreditLabel = new qx.ui.basic.Label().set({
          value: pair[1] + " $",
          alignX: "center",
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

      const vatTitle = new qx.ui.basic.Label().set({
        value: "VAT 7.7%",
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
        converter: totalPrice => (totalPrice*0.077).toFixed(2) + " $"
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
            osparc.component.message.FlashMessenger.getInstance().logAs(msg, "INFO", null, 10000);
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
            osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR", null, 10000);
          });
          paymentGateway.addListener("close", () => win.close());
        }, 1000);
      });
      return buyBtn;
    },

    __getCreditsExplanation: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20));

      const label1 = new qx.ui.basic.Label().set({
        value: "Here we explain what you can run/do with credits.",
        font: "text-16",
        rich: true,
        wrap: true
      });
      layout.add(label1);

      const label2 = new qx.ui.basic.Label().set({
        value: "They can be used for:<br>- using the GUI<br>- modeling<br>- running solvers<br>- transfer data<br>- import VIP models?<br>- collaboration?",
        font: "text-16",
        rich: true,
        wrap: true
      });
      layout.add(label2);

      const label3 = new qx.ui.basic.Label().set({
        value: "<i>If something goes wrong you won't be charged</i>",
        font: "text-16",
        rich: true,
        wrap: true
      });
      layout.add(label3);

      return layout;
    }
  }
});
