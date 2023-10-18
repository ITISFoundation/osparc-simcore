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

qx.Class.define("osparc.desktop.credits.UserCenterWindow", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function(walletsEnabled = false) {
    this.base(arguments, "credits", this.tr("User Center"));

    const viewWidth = walletsEnabled ? 1000 : 800;
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
      const accountWindow = new osparc.desktop.credits.UserCenterWindow(walletsEnabled);
      accountWindow.center();
      accountWindow.open();
      return accountWindow;
    }
  },

  members: {
    __userCenter: null,

    openOverview: function() {
      return this.__userCenter.openOverview();
    },

    openProfile: function() {
      return this.__userCenter.openProfile();
    },

    openWallets: function() {
      return this.__userCenter.openWallets();
    }
  }
});
