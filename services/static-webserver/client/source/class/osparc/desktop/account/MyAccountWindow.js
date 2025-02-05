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

qx.Class.define("osparc.desktop.account.MyAccountWindow", {
  extend: osparc.ui.window.TabbedWindow,

  construct: function() {
    this.base(arguments, "credits", this.tr("My Account"));

    const width = 990;
    const height = 700;
    const maxHeight = 700;
    this.set({
      width,
      height,
      maxHeight,
    });

    const myAccount = this.__myAccount = new osparc.desktop.account.MyAccount();
    this._setTabbedView(myAccount);
  },

  statics: {
    openWindow: function() {
      const accountWindow = new osparc.desktop.account.MyAccountWindow();
      accountWindow.center();
      accountWindow.open();
      return accountWindow;
    }
  },

  members: {
    __myAccount: null,

    openTags: function() {
      this.__myAccount.openTags();
    },
  }
});
