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

qx.Class.define("osparc.desktop.paymentMethods.PaymentMethodListItem", {
  extend: osparc.ui.list.ListItem,

  construct: function() {
    this.base(arguments);

    const layout = this._getLayout();
    layout.setSpacingX(15);
    layout.setColumnFlex(this.self().GRID_POS.ICON, 0);
    layout.setColumnFlex(this.self().GRID_POS.NAME, 0);
    layout.setColumnFlex(this.self().GRID_POS.TYPE, 0);
    layout.setColumnFlex(this.self().GRID_POS.MASKED_NUMBER, 0);
    layout.setColumnFlex(this.self().GRID_POS.EXPIRATION_DATE, 1);
    // buttons to the right
    layout.setColumnFlex(this.self().GRID_POS.INFO_BUTTON, 0);
    layout.setColumnFlex(this.self().GRID_POS.DELETE_BUTTON, 0);

    this.getChildControl("thumbnail").setSource("@FontAwesome5Solid/credit-card/18");

    const cardHolderName = this.getChildControl("card-holder-name");
    this.bind("cardHolderName", cardHolderName, "value");

    const cardType = this.getChildControl("card-type");
    this.bind("cardType", cardType, "value");

    const cardNumberMasked = this.getChildControl("card-number-masked");
    this.bind("cardNumberMasked", cardNumberMasked, "value");

    const expirationDate = this.getChildControl("expiration-date");
    this.bind("expirationMonth", expirationDate, "value", {
      converter: month => month + "/" + this.getExpirationYear()
    });
    this.bind("expirationYear", expirationDate, "value", {
      converter: year => this.getExpirationMonth() + "/" + year
    });

    this.getChildControl("details-button");
    this.getChildControl("delete-button");
  },

  properties: {
    walletId: {
      check: "Number",
      init: null,
      nullable: false,
      event: "changeWalletId"
    },

    cardHolderName: {
      check: "String",
      init: "null",
      nullable: false,
      event: "changeCardHolderName"
    },

    cardType: {
      check: "String",
      init: "null",
      nullable: false,
      event: "changeCardType"
    },

    cardNumberMasked: {
      check: "String",
      init: "null",
      nullable: false,
      event: "changeCardNumberMasked"
    },

    expirationMonth: {
      check: "Number",
      init: null,
      nullable: false,
      event: "changeExpirationMonth"
    },

    expirationYear: {
      check: "Number",
      init: null,
      nullable: false,
      event: "changeExpirationYear"
    }
  },

  events: {
    "openPaymentMethodDetails": "qx.event.type.Data",
    "deletePaymentMethod": "qx.event.type.Data"
  },

  statics: {
    GRID_POS: {
      ICON: 0,
      NAME: 1,
      TYPE: 2,
      MASKED_NUMBER: 3,
      EXPIRATION_DATE: 4,
      INFO_BUTTON: 5,
      DELETE_BUTTON: 6
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "card-holder-name":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: this.self().GRID_POS.NAME
          });
          break;
        case "card-type":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: this.self().GRID_POS.TYPE
          });
          break;
        case "card-number-masked":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: this.self().GRID_POS.MASKED_NUMBER
          });
          break;
        case "expiration-date":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: this.self().GRID_POS.EXPIRATION_DATE
          });
          break;
        case "details-button":
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/info/14"
          });
          control.addListener("execute", () => this.fireDataEvent("openPaymentMethodDetails", this.getKey()));
          this._add(control, {
            row: 0,
            column: this.self().GRID_POS.INFO_BUTTON
          });
          break;
        case "delete-button":
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/trash/14"
          });
          control.addListener("execute", () => this.__deletePressed());
          this._add(control, {
            row: 0,
            column: this.self().GRID_POS.DELETE_BUTTON
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __deletePressed: function() {
      const msg = this.tr("Are you sure you want to delete the Payment Method?");
      const win = new osparc.ui.window.Confirmation(msg).set({
        caption: this.tr("Delete Payment Method"),
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      win.center();
      win.open();
      win.addListener("close", () => {
        if (win.getConfirmed()) {
          this.fireDataEvent("deletePaymentMethod", this.getKey());
        }
      });
    }
  }
});
