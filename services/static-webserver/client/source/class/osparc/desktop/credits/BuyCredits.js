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
    wallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: false,
      event: "changeWallet",
      apply: "__applyWallet"
    },

    nCredits: {
      check: "Number",
      init: 50,
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
        case "wallet-info": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          const label = new qx.ui.basic.Label().set({
            value: this.tr("Wallets:"),
            font: "text-14"
          });
          control.add(label);
          this.getChildControl("left-side").add(control);
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
      // this.getChildControl("credit-offers-view");
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
      const vLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const label = new qx.ui.basic.Label().set({
        value: this.tr("Credits:"),
        font: "text-14"
      });
      vLayout.add(label);

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

      const walletTitle = new qx.ui.basic.Label().set({
        value: "Wallet",
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
        converter: wallet => wallet ? wallet.getName() : this.tr("Select Wallet")
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

      const buying = () => {
        buyBtn.set({
          fetching: true,
          label: this.tr("Buying...")
        });
      };
      const transactionFinished = () => {
        buyBtn.set({
          fetching: false,
          label: this.tr("Buy Credits")
        });
      };
      buyBtn.addListener("execute", () => {
        const nCredits = this.getNCredits();
        const totalPrice = this.getTotalPrice();
        const wallet = this.getWallet();
        buying();
        setTimeout(() => {
          if (nCredits < 100) {
            let url = "https://www.payment.appmotion.de";
            url += "/pay?id=2";

            const paymentGateway = new osparc.desktop.credits.PaymentGateway().set({
              url,
              nCredits,
              totalPrice,
              walletName: wallet.getName()
            });
            const title = "AppMotion's middleware";
            const win = osparc.ui.window.Window.popUpInWindow(paymentGateway, title, 320, 475);
            win.center();
            win.open();
            paymentGateway.addListener("paymentSuccessful", () => {
              transactionFinished();
              let msg = "Payment Successful";
              msg += "<br>";
              msg += "You now have " + nCredits + " more credits";
              osparc.component.message.FlashMessenger.getInstance().logAs(msg, "INFO", null, 10000);
              wallet.setCreditsAvailable(wallet.getCreditsAvailable() + nCredits);
              this.fireDataEvent("transactionSuccessful", {
                nCredits,
                totalPrice,
                walletName: wallet.getName()
              });
            });
            paymentGateway.addListener("paymentFailed", () => {
              transactionFinished();
              let msg = "Payment Failed";
              msg += "<br>";
              msg += "Please try again";
              osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR", null, 10000);
            });
            paymentGateway.addListener("close", () => {
              win.close();
              transactionFinished();
            });
          } else {
            transactionFinished();

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
            this.__pgWindow = qx.bom.Window.open(
              "https://www.sandbox.paypal.com/checkoutnow?sessionID=uid_528c54d94a_mti6mty6mzk&buttonSessionID=uid_fd2db9090d_mti6mty6mzk&stickinessID=uid_b4ee25a7cf_mdc6nta6ntq&smokeHash=&token=6XJ77332V85719833&fundingSource=paypal&buyerCountry=GB&locale.x=en_GB&commit=false&enableFunding.0=paylater&clientID=Ac9r0wZ444AH4c8nEvA7l5QbBaGtf8B0y2ZSTGvQDXFNb0HlkFb9cseCUWMZ0_mJUJPfd2NYjJx4HYLI&env=sandbox&sdkMeta=eyJ1cmwiOiJodHRwczovL3d3dy5wYXlwYWwuY29tL3Nkay9qcz9jbGllbnQtaWQ9QWM5cjB3WjQ0NEFINGM4bkV2QTdsNVFiQmFHdGY4QjB5MlpTVEd2UURYRk5iMEhsa0ZiOWNzZUNVV01aMF9tSlVKUGZkMk5Zakp4NEhZTEkmY29tbWl0PWZhbHNlJmN1cnJlbmN5PUdCUCZkaXNhYmxlLWZ1bmRpbmc9Y2FyZCZlbmFibGUtZnVuZGluZz1wYXlsYXRlciZidXllci1jb3VudHJ5PUdCJmxvY2FsZT1lbl9HQiZjb21wb25lbnRzPW1lc3NhZ2VzLGJ1dHRvbnMiLCJhdHRycyI6eyJkYXRhLXVpZCI6InVpZF9iZnZyaHB5ZXZ4ZXF1aXVpc2FodHJiamhpb3piangifX0&xcomponent=1&version=5.0.394",
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

            blockerDomEl.addEventListener("click", () => this.__pgWindow.focus());
          }
        }, 3000);
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
