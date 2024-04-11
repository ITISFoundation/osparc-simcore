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
  extend: osparc.ui.window.TabbedWindow,

  construct: function() {
    this.base(arguments, "credits", this.tr("My Account"));

    const width = 900;
    const height = 600;
    this.set({
      width,
      height
    });

    const myAccount = this.__myAccount = new osparc.desktop.credits.MyAccount();
    this._setTabbedView(myAccount);
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
