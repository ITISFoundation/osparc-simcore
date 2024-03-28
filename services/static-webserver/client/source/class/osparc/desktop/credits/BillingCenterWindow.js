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

qx.Class.define("osparc.desktop.credits.BillingCenterWindow", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    const caption = this.tr("Billing Center");
    this.base(arguments, "credits", caption);

    const viewWidth = 1035;
    const viewHeight = 700;

    this.set({
      layout: new qx.ui.layout.Grow(),
      modal: true,
      width: viewWidth,
      height: viewHeight,
      showMaximize: false,
      showMinimize: false,
      resizable: true,
      appearance: "service-window"
    });

    const billingCenter = this.__billingCenter = new osparc.desktop.credits.BillingCenter();
    this.add(billingCenter);
  },

  statics: {
    openWindow: function() {
      const accountWindow = new osparc.desktop.credits.BillingCenterWindow();
      accountWindow.center();
      accountWindow.open();
      return accountWindow;
    }
  },

  members: {
    __billingCenter: null,

    openWallets: function() {
      return this.__billingCenter.openWallets();
    },

    openPaymentMethods: function() {
      this.__billingCenter.openPaymentMethods();
    },

    openTransactions: function() {
      this.__billingCenter.openTransactions();
    },

    openUsage: function() {
      this.__billingCenter.openUsage();
    }
  }
});
