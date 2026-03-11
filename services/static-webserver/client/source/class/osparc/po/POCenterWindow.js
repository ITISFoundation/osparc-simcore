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

qx.Class.define("osparc.po.POCenterWindow", {
  extend: osparc.ui.window.TabbedWindow,

  construct: function(openPage) {
    this.base(arguments, "po-center", this.tr("PO Center"));

    const width = 1050;
    const height = 700;
    this.set({
      width,
      height
    });

    const poCenter = new osparc.po.POCenter(openPage);
    this._setTabbedView(poCenter);
  },

  statics: {
    openWindow: function(openPage) {
      const accountWindow = new osparc.po.POCenterWindow(openPage);
      accountWindow.center();
      accountWindow.open();
      return accountWindow;
    }
  }
});
