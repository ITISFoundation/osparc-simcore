/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.admin.AdminCenterWindow", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    this.base(arguments, "admin-center", this.tr("Admin Center"));

    const viewWidth = 800;
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

    const adminCenter = new osparc.admin.AdminCenter();
    this.add(adminCenter);
  },

  statics: {
    openWindow: function() {
      const accountWindow = new osparc.admin.AdminCenterWindow();
      accountWindow.center();
      accountWindow.open();
      return accountWindow;
    }
  }
});
