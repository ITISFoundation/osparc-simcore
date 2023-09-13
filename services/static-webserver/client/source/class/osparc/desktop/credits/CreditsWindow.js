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

qx.Class.define("osparc.desktop.credits.CreditsWindow", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function(walletsEnabled = false) {
    this.base(arguments, "credits", this.tr("User Center"));

    const viewWidth = walletsEnabled ? 1050 : 800;
    const viewHeight = walletsEnabled ? 700 : 600;

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

    const userCenter = this.__userCenter = new osparc.desktop.credits.UserCenter(walletsEnabled);
    this.add(userCenter);
  },

  statics: {
    openWindow: function(walletsEnabled = false) {
      const accountWindow = new osparc.desktop.credits.CreditsWindow(walletsEnabled);
      accountWindow.center();
      accountWindow.open();
      return accountWindow;
    }
  },

  members: {
    __userCenter: null,

    openOverview: function() {
      this.__userCenter.openOverview();
    },

    openWallets: function() {
      this.__userCenter.openWallets();
    }
  }
});
