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
  extend: osparc.ui.window.TabbedWindow,

  construct: function() {
    this.base(arguments, "credits", this.tr("Billing Center"));


    osparc.utils.Utils.setIdToWidget(this, "billingCenterWindow");

    const width = 1035;
    const height = 700;
    this.set({
      width,
      height
    })

    const billingCenter = this.__billingCenter = new osparc.desktop.credits.BillingCenter();
    this._setTabbedView(billingCenter);
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
