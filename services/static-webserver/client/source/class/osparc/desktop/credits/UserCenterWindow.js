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

  construct: function() {
    const caption = this.tr("User Center");
    this.base(arguments, "credits", caption);

    const viewWidth = 900;
    const viewHeight = 600;

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

    const userCenter = this.__userCenter = new osparc.desktop.credits.UserCenter();
    this.add(userCenter);
  },

  statics: {
    openWindow: function() {
      const accountWindow = new osparc.desktop.credits.UserCenterWindow();
      accountWindow.center();
      accountWindow.open();
      return accountWindow;
    }
  },

  members: {
    __userCenter: null,

    openProfile: function() {
      return this.__userCenter.openProfile();
    }
  }
});
