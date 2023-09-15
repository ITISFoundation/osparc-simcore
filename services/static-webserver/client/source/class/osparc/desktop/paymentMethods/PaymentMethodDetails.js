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

qx.Class.define("osparc.desktop.paymentMethods.PaymentMethodDetails", {
  extend: qx.ui.core.Widget,

  construct: function(paymentMethodData) {
    this.base(arguments);

    const grid = new qx.ui.layout.Grid(20, 10);
    grid.setColumnAlign(0, "rightt", "middle"); // resource limit value
    this._setLayout(grid);

    this.__buildLayout(paymentMethodData);
  },

  statics: {
    popUpInWindow: function(paymentMethodData) {
      const title = qx.locale.Manager.tr("Payment Method details");
      const paymentMethodDetails = new osparc.desktop.paymentMethods.PaymentMethodDetails(paymentMethodData);
      const viewWidth = 300;
      const viewHeight = 300;
      const win = osparc.ui.window.Window.popUpInWindow(paymentMethodDetails, title, viewWidth, viewHeight);
      win.center();
      win.open();
      return win;
    }
  },

  members: {
    __buildLayout: function(paymentMethodData) {
      [
        [this.tr("Holder name"), paymentMethodData["cardHolderName"]],
        [this.tr("Type"), paymentMethodData["cardType"]],
        [this.tr("Number"), paymentMethodData["cardHoldecardNumberMaskedrName"]],
        [this.tr("Expiration date"), paymentMethodData["expirationMonth"] + "/" + paymentMethodData["expirationYear"]],
        [this.tr("Address"), paymentMethodData["streetAddress"]],
        [this.tr("ZIP code"), paymentMethodData["zipcode"]],
        [this.tr("Country"), paymentMethodData["country"]]
      ].forEach((pair, idx) => {
        this._add(new qx.ui.basic.Label(pair[0]).set({
          font: "text-14"
        }), {
          row: idx,
          column: 0
        });
        this._add(new qx.ui.basic.Label(pair[1]).set({
          font: "text-14"
        }), {
          row: idx,
          column: 1
        });
      });
    }
  }
});
