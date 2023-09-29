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
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    this.base(arguments, "po-center", this.tr("PO Center"));

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

    const poCenter = this.__poCenter = new osparc.po.POCenter();
    this.add(poCenter);
  },

  statics: {
    openWindow: function() {
      const accountWindow = new osparc.po.POCenterWindow();
      accountWindow.center();
      accountWindow.open();
      return accountWindow;
    }
  },

  members: {
    __poCenter: null,

    openInvitations: function() {
      this.__poCenter.openInvitations();
    }
  }
});
