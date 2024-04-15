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
  extend: osparc.ui.window.TabbedWindow,

  construct: function() {
    this.base(arguments, "admin-center", this.tr("Admin Center"));

    const width = 800;
    const height = 600;
    this.set({
      width: width,
      height: height,
    });

    const adminCenter = new osparc.admin.AdminCenter();
    this._setTabbedView(adminCenter);
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
