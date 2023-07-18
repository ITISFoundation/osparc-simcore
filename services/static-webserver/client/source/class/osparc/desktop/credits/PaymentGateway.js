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

    this._setLayout(new qx.ui.layout.VBox(10));

    this.getChildControl("url-field");
    this.getChildControl("header-logo");
    this.initPaymentStatus();
  },

  properties: {
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
      event: "__updateMessage"
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
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
            alignX: "center",
            maxWidth: 400
          });
          const image = new qx.ui.basic.Image("osparc/s4l_logo.png").set({
            maxWidth: 200,
            alignX: "center",
            scale: true
          });
          control.add(image);
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
          const label = new qx.ui.basic.Label().set({
            value: "Pay"
          });
          control.add(label);
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

    __updateMessage: function() {
      console.log("updateMessage");
    }
  }
});
