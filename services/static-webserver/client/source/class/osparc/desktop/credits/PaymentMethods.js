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

qx.Class.define("osparc.desktop.credits.PaymentMethods", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    this.getChildControl("intro-text");
    this.getChildControl("payment-methods-list-layout");

    this.__fetchPaymentMethods();
  },

  properties: {
    paymentMethods: {
      check: "Array",
      init: [],
      nullable: false,
      apply: "__applyPaymentMethods"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "intro-text":
          control = new qx.ui.basic.Label().set({
            value: this.tr("Intro text about payment methods"),
            font: "text-14",
            rich: true,
            wrap: true
          });
          break;
        case "payment-methods-list-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
          break;
      }
      return control || this.base(arguments, id);
    },

    __fetchPaymentMethods: function() {
      const listLayout = this.getChildControl("payment-methods-list-layout");
      listLayout.removeAll();

      listLayout.add(new qx.ui.basic.Label().set({
        value: this.tr("Fetching Payment Methods"),
        font: "text-14",
        rich: true,
        wrap: true
      }));

      const promises = [];
      const wallets = osparc.store.Store.getInstance().getWallets();
      wallets.forEach(wallet => {
        if (wallet.getMyAccessRights()["write"]) {
          const params = {
            url: {
              walletId: wallet.getWalletId()
            }
          };
          promises.push(osparc.data.Resources.fetch("payments-methods", "get", params));
        }
      });
      Promise.all(promises)
        .then(paymentMethods => {
          listLayout.removeAll();
          if (paymentMethods.length) {
            paymentMethods.forEach(paymentMethod => console.log(paymentMethod));
          } else {
            listLayout.add(new qx.ui.basic.Label().set({
              value: this.tr("No Payment Methods found"),
              font: "text-14",
              rich: true,
              wrap: true
            }));
          }
        })
        .catch(err => console.error(err));
    }
  }
});
