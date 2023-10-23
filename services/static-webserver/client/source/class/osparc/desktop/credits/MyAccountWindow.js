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

qx.Class.define("osparc.desktop.credits.MyAccountWindow", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    const caption = this.tr("My Account");
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

    const myAccount = this.__myAccount = new osparc.desktop.credits.MyAccount();
    this.add(myAccount);
  },

  statics: {
    openWindow: function() {
      const accountWindow = new osparc.desktop.credits.MyAccountWindow();
      accountWindow.center();
      accountWindow.open();
      return accountWindow;
    }
  },

  members: {
    __myAccount: null,

    openProfile: function() {
      return this.__myAccount.openProfile();
    }
  }
});
