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
      check: "Number",
      init: null,
      nullable: false,
      event: "changeUrl"
    },

    paymentStatus: {
      check: [null, true, false],
      init: null,
      nullable: false,
      apply: "__applyPaymentStatus"
    },

    nCredits: {
      check: "Number",
      init: 1,
      nullable: false,
      event: "changeNCredits",
      apply: "__updateMessage"
    },

    totalPrice: {
      check: "Number",
      init: null,
      nullable: false,
      event: "changeTotalPrice",
      apply: "__updateMessage"
    }
  },

  events: {
    "paymentSuccessful": "qx.event.type.Data",
    "paymentFailed": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "url-field":
          control = new qx.ui.form.TextField().set({
            value: "https://www.3rdparty.service.payment.io",
            backgroundColor: "white",
            enabled: false
          });
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
            padding: 10
          });

          const hbox1 = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
          const creditsTitle = new qx.ui.basic.Label().set({
            value: this.tr("Number of credits:"),
            font: "text-14"
          });
          hbox1.add(creditsTitle);
          hbox1.add(new qx.ui.core.Spacer(), {
            flex: 1
          });
          const creditsLabel = new qx.ui.basic.Label().set({
            value: this.tr("Sim4Life credits"),
            font: "text-16"
          });
          this.bind("nCredits", creditsLabel, "value");
          hbox1.add(creditsLabel);
          control.add(hbox1);

          const hbox2 = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
          const totalTitle = new qx.ui.basic.Label().set({
            value: this.tr("Total"),
            font: "text-14"
          });
          hbox2.add(totalTitle);
          hbox2.add(new qx.ui.core.Spacer(), {
            flex: 1
          });
          const totalLabel = new qx.ui.basic.Label().set({
            value: this.tr("Sim4Life credits"),
            font: "text-16"
          });
          this.bind("totalPrice", totalLabel, "value", {
            converter: val => val + " $"
          });
          hbox2.add(totalLabel);
          control.add(hbox2);

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
            alignX: "center",
            maxWidth: 400
          });
          const label = new qx.ui.basic.Label().set({
            value: "Payment Successful"
          });
          control.add(label);
          this.getChildControl("content-stack").add(control);
          break;
        }
        case "payment-failed": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            alignX: "center",
            maxWidth: 400
          });
          const label = new qx.ui.basic.Label().set({
            value: "Payment failed"
          });
          control.add(label);
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
      const groupBox = new qx.ui.groupbox.GroupBox("Complete purchase");
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

      // name
      const nameLabel = new qx.ui.basic.Label("Name:");
      groupBox.add(nameLabel, {
        row: 0,
        column: 0
      });

      const nameTextfield = new qx.ui.form.TextField();
      groupBox.add(nameTextfield, {
        row: 0,
        column: 1
      });

      // gender
      const genderLabel = new qx.ui.basic.Label("Gender:");
      groupBox.add(genderLabel, {
        row: 1,
        column: 0
      });

      const genderSelectBox = new qx.ui.form.SelectBox();
      const dummyItem = new qx.ui.form.ListItem("-please select-", null, "X");
      genderSelectBox.add(dummyItem);
      const maleItem = new qx.ui.form.ListItem("male", null, "M");
      genderSelectBox.add(maleItem);
      const femaleItem = new qx.ui.form.ListItem("female", null, "F");
      genderSelectBox.add(femaleItem);
      groupBox.add(genderSelectBox, {
        row: 1,
        column: 1
      });

      // serialize button
      const sendButton = new qx.ui.form.Button("Send");
      groupBox.add(sendButton, {
        row: 3,
        column: 0
      });

      return groupBox;
    },

    __updateMessage: function() {
      console.log("updateMessage");
    }
  }
});
