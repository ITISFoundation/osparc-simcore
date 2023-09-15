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
    layout.setColumnFlex(5, 1);
    layout.setColumnFlex(6, 0);

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

    const store = osparc.store.Store.getInstance();
    const walletName = this.getChildControl("wallet-name");
    this.bind("walletId", walletName, "value", {
      converter: walletId => {
        const found = store.getWallets().find(wallet => wallet.getWalletId() === walletId);
        return found ? found.getName() : this.tr("Unknown Credit Account");
      }
    });

    this.__getOptionsMenu();
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
            column: 1,
            rowSpan: 2
          });
          break;
        case "card-type":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: 2,
            rowSpan: 2
          });
          break;
        case "card-number-masked":
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
        case "wallet-name":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: 5,
            rowSpan: 2
          });
          break;
        case "options-menu": {
          const iconSize = 26;
          control = new qx.ui.form.MenuButton().set({
            maxWidth: iconSize,
            maxHeight: iconSize,
            alignX: "center",
            alignY: "middle",
            icon: "@FontAwesome5Solid/ellipsis-v/"+(iconSize-11),
            focusable: false
          });
          this._add(control, {
            row: 0,
            column: 6,
            rowSpan: 2
          });
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    // overridden
    __getOptionsMenu: function() {
      const optionsMenu = this.getChildControl("options-menu");
      optionsMenu.show();

      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const viewDetailsButton = new qx.ui.menu.Button(this.tr("View details..."));
      viewDetailsButton.addListener("execute", () => this.fireDataEvent("openPaymentMethodDetails", this.getKey()));
      menu.add(viewDetailsButton);

      const detelePMButton = new qx.ui.menu.Button(this.tr("Delete Payment Method"));
      detelePMButton.addListener("execute", () => {
        const msg = this.tr("Are you sure you want to delete the Payment Method?");
        const win = new osparc.ui.window.Confirmation(msg).set({
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
      }, this);
      menu.add(detelePMButton);

      optionsMenu.setMenu(menu);

      return menu;
    }
  }
});
