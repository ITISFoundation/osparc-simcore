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
  extend: osparc.ui.list.ListItemWithMenu,

  construct: function() {
    this.base(arguments);

    const layout = this._getLayout();
    layout.setSpacingX(15);
    layout.setColumnFlex(1, 0);
    layout.setColumnFlex(2, 0);
    layout.setColumnFlex(3, 0);
    layout.setColumnFlex(4, 0);

    this.getChildControl("thumbnail").setSource("@FontAwesome5Solid/credit-card/16");

    const cardType = this.getChildControl("card-type");
    this.bind("cardType", cardType, "value");

    const cardNumberMasked = this.getChildControl("card-number-masked");
    this.bind("cardNumberMasked", cardNumberMasked, "value");

    const cardHolderName = this.getChildControl("card-holder-name");
    this.bind("cardHolderName", cardHolderName, "value");

    const expirationDate = this.getChildControl("expiration-date");
    this.bind("expirationMonth", expirationDate, "value", {
      converter: month => month + "/" + this.getExpirationYear()
    });
    this.bind("expirationYear", expirationDate, "value", {
      converter: year => this.getExpirationMonth() + "/" + year
    });
  },

  properties: {
    walletId: {
      check: "Number",
      init: null,
      nullable: false
    },

    idr: {
      check: "String",
      init: null,
      nullable: false
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

    cardHolderName: {
      check: "String",
      init: "null",
      nullable: false,
      event: "changeCardHolderName"
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

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "card-type":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: 1,
            rowSpan: 2
          });
          break;
        case "card-number-masked":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: 2,
            rowSpan: 2
          });
          break;
        case "card-holder-name":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: 3,
            rowSpan: 2
          });
          break;
        case "expiration-date":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: 4,
            rowSpan: 2
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    // overridden
    _getOptionsMenu: function() {
      const optionsMenu = this.getChildControl("options");
      optionsMenu.show();

      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const viewDetailsButton = new qx.ui.menu.Button(this.tr("View details..."));
      viewDetailsButton.addListener("execute", () => this.fireDataEvent("openPaymentMethodDetails", this.getKey()));
      menu.add(viewDetailsButton);

      const editWalletButton = new qx.ui.menu.Button(this.tr("Edit details..."));
      editWalletButton.addListener("execute", () => this.fireDataEvent("deletePaymentMethod", this.getKey()));
      menu.add(editWalletButton);

      return menu;
    }
  }
});
