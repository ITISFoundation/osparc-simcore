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

qx.Class.define("osparc.tester.TesterCenterWindow", {
  extend: osparc.ui.window.TabbedWindow,

  construct: function() {
    this.base(arguments, "tester-center", this.tr("Tester Center"));

    const width = 800;
    const maxHeight = 800;
    this.set({
      width,
      maxHeight,
    });

    const testerCenter = new osparc.tester.TesterCenter();
    this._setTabbedView(testerCenter);
  },

  statics: {
    openWindow: function() {
      const accountWindow = new osparc.tester.TesterCenterWindow();
      accountWindow.center();
      accountWindow.open();
      return accountWindow;
    }
  }
});
