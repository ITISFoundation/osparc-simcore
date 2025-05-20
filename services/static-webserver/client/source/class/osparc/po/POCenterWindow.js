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

  construct: function() {
    this.base(arguments, "po-center", this.tr("PO Center"));

    const width = 900;
    const height = 600;
    this.set({
      width,
      height
    });

    const poCenter = new osparc.po.POCenter();
    this._setTabbedView(poCenter);
  },

  statics: {
    openWindow: function() {
      const accountWindow = new osparc.po.POCenterWindow();
      accountWindow.center();
      accountWindow.open();
      return accountWindow;
    }
  }
});
