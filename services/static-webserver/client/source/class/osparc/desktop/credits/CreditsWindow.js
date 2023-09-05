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

    this.add(new osparc.desktop.credits.UserCenter(walletsEnabled));
  },

  statics: {
    openWindow: function(walletsEnabled = false) {
      const accountWindow = new osparc.desktop.credits.CreditsWindow(walletsEnabled);
      accountWindow.center();
      accountWindow.open();
      return accountWindow;
    }
  }
});
