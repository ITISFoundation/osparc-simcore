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

qx.Class.define("osparc.desktop.credits.PaymentGateway", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.getChildControl("url-field");
    this.getChildControl("header-logo");
    this.getChildControl("header-message");
    this.initPaymentStatus();
  },

  properties: {
    url: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeUrl"
    },

    nCredits: {
      check: "Number",
      init: 1,
      nullable: false,
      event: "changeNCredits"
    },

    totalPrice: {
      check: "Number",
      init: null,
      nullable: false,
      event: "changeTotalPrice"
    },

    walletName: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeWalletName"
    },

    paymentStatus: {
      check: [null, true, false],
      init: null,
      nullable: false,
      apply: "__applyPaymentStatus"
    }
  },

  events: {
    "paymentSuccessful": "qx.event.type.Event",
    "paymentFailed": "qx.event.type.Event",
    "close": "qx.event.type.Event"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "url-field":
          control = new qx.ui.form.TextField().set({
            textColor: "black",
            backgroundColor: "white"
          });
          this.bind("url", control, "value");
          this._add(control);
          break;
        case "header-logo": {
          control = new qx.ui.basic.Image("osparc/s4l_logo.png").set({
            width: 120,
            height: 60,
            alignX: "center",
            scale: true
          });
          this._add(control);
          break;
        }
        case "header-message": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            alignX: "center",
            padding: 10
          });

          const nCreditsHBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
            alignX: "center",
            maxWidth: 200
          });
          const creditsTitle = new qx.ui.basic.Label().set({
            value: this.tr("Number of credits:"),
            font: "text-14"
          });
          nCreditsHBox.add(creditsTitle);
          nCreditsHBox.add(new qx.ui.core.Spacer(), {
            flex: 1
          });
          const creditsLabel = new qx.ui.basic.Label().set({
            value: this.tr("Sim4Life credits"),
            font: "text-16"
          });
          this.bind("nCredits", creditsLabel, "value");
          nCreditsHBox.add(creditsLabel);
          control.add(nCreditsHBox);

          const walletNameHBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
            alignX: "center",
            maxWidth: 200
          });
          const walletNameTitle = new qx.ui.basic.Label().set({
            value: this.tr("Wallet:"),
            font: "text-14"
          });
          walletNameHBox.add(walletNameTitle);
          walletNameHBox.add(new qx.ui.core.Spacer(), {
            flex: 1
          });
          const walletNameLabel = new qx.ui.basic.Label().set({
            value: this.tr("Sim4Life credits"),
            font: "text-16"
          });
          this.bind("walletName", walletNameLabel, "value");
          walletNameHBox.add(walletNameLabel);
          control.add(walletNameHBox);

          const totalHBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
            alignX: "center",
            maxWidth: 200
          });
          const totalTitle = new qx.ui.basic.Label().set({
            value: this.tr("Total"),
            font: "text-14"
          });
          totalHBox.add(totalTitle);
          totalHBox.add(new qx.ui.core.Spacer(), {
            flex: 1
          });
          const totalLabel = new qx.ui.basic.Label().set({
            value: this.tr("Sim4Life credits"),
            font: "text-16"
          });
          this.bind("totalPrice", totalLabel, "value", {
            converter: val => val + " $"
          });
          totalHBox.add(totalLabel);
          control.add(totalHBox);

          this._add(control);
          break;
        }
        case "content-stack":
          control = new qx.ui.container.Stack();
          this._add(control, {
            flex: 1
          });
          break;
        case "credit-card-view": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            alignX: "center",
            maxWidth: 400
          });
          control.add(this.__getCreditCardForm());
          this.getChildControl("content-stack").add(control);
          break;
        }
        case "payment-successful": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            padding: 10
          });

          const label = new qx.ui.basic.Atom().set({
            label: "Payment Successful",
            icon: "@FontAwesome5Solid/check/12",
            font: "text-18",
            alignX: "center"
          });
          control.add(label);

          const closeButton = new qx.ui.form.Button("Close");
          closeButton.addListener("execute", () => this.fireEvent("close"));
          control.add(closeButton);

          this.getChildControl("content-stack").add(control);
          break;
        }
        case "payment-failed": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            padding: 10
          });

          const label = new qx.ui.basic.Atom().set({
            label: "Payment failed",
            icon: "@FontAwesome5Solid/times/12",
            font: "text-18",
            alignX: "center"
          });
          control.add(label);

          const closeButton = new qx.ui.form.Button("Close");
          closeButton.addListener("execute", () => this.fireEvent("close"));
          control.add(closeButton);

          this.getChildControl("content-stack").add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __applyPaymentStatus: function(value) {
      let page = null;
      switch (value) {
        case true:
          page = this.getChildControl("payment-successful");
          break;
        case false:
          page = this.getChildControl("payment-failed");
          break;
        default:
          page = this.getChildControl("credit-card-view");
          break;
      }
      this.getChildControl("content-stack").setSelection([page]);
    },

    __getCreditCardForm: function() {
      const groupBox = new qx.ui.groupbox.GroupBox("Pay by Credit Card");
      groupBox.getChildControl("legend").set({
        font: "text-14"
      });
      groupBox.getChildControl("frame").set({
        backgroundColor: "transparent"
      });

      const grid = new qx.ui.layout.Grid();
      grid.setSpacing(5);
      grid.setColumnAlign(0, "left", "middle");
      groupBox.setLayout(grid);

      let row = 0;

      // name
      const nameLabel = new qx.ui.basic.Label("Name");
      groupBox.add(nameLabel, {
        row,
        column: 0
      });
      row++;

      const nameTextfield = new qx.ui.form.TextField();
      groupBox.add(nameTextfield, {
        row,
        column: 0,
        colSpan: 4
      });
      row++;

      // number
      const numberLabel = new qx.ui.basic.Label("Number");
      groupBox.add(numberLabel, {
        row,
        column: 0
      });
      row++;

      const numberTextfield = new qx.ui.form.TextField();
      groupBox.add(numberTextfield, {
        row,
        column: 0,
        colSpan: 4
      });
      row++;

      const edLabel = new qx.ui.basic.Label("Expiration date");
      groupBox.add(edLabel, {
        row,
        column: 0
      });
      const cvvLabel = new qx.ui.basic.Label("CVV");
      groupBox.add(cvvLabel, {
        row,
        column: 2
      });
      row++;

      const edMSelectBox = new qx.ui.form.SelectBox().set({
        maxWidth: 100
      });
      [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "Movember",
        "December"
      ].forEach(month => {
        const dummyItem = new qx.ui.form.ListItem(month, null, month);
        edMSelectBox.add(dummyItem);
      });
      groupBox.add(edMSelectBox, {
        row,
        column: 0
      });

      const edDSelectBox = new qx.ui.form.SelectBox().set({
        maxWidth: 40
      });
      [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31].forEach(day => {
        const dummyItem = new qx.ui.form.ListItem(day.toString(), null, day);
        edDSelectBox.add(dummyItem);
      });
      groupBox.add(edDSelectBox, {
        row,
        column: 1
      });

      const cvvTextfield = new qx.ui.form.TextField();
      groupBox.add(cvvTextfield, {
        row,
        column: 2
      });
      row++;

      // serialize button
      const buyBtn = new osparc.ui.form.FetchButton().set({
        label: this.tr("Buy"),
        font: "text-16",
        appearance: "strong-button",
        maxWidth: 150,
        center: true
      });
      groupBox.add(buyBtn, {
        row,
        column: 0
      });
      buyBtn.addListener("execute", () => {
        buyBtn.setFetching(true);
        setTimeout(() => {
          buyBtn.setFetching(false);
          if (this.getNCredits() === 42) {
            this.fireEvent("paymentFailed");
            this.setPaymentStatus(false);
          } else {
            this.fireEvent("paymentSuccessful");
            this.setPaymentStatus(true);
          }
        }, 3000);
      });

      return groupBox;
    }
  }
});
