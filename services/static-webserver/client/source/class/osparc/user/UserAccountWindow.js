/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.user.UserAccountWindow", {
  extend: osparc.ui.window.TabbedWindow,

  construct: function(userGroupId) {
    this.base(arguments, "user-account-"+userGroupId, this.tr("User Account"));

    this.set({
      width: osparc.user.UserAccountWindow.WIDTH,
      height: osparc.user.UserAccountWindow.HEIGHT,
    });

    const userAccount = new osparc.user.UserAccount(userGroupId);
    userAccount.addListener("updateCaption", e => this.setCaption(e.getData()));
    userAccount.addListener("closeWindow", () => this.close(), this);
    this._setTabbedView(userAccount);
  },

  statics: {
    WIDTH: 500,
    HEIGHT: 500,

    openWindow: function(userGroupId) {
      const userAccountWindow = new osparc.user.UserAccountWindow(userGroupId);
      userAccountWindow.center();
      userAccountWindow.open();
      return userAccountWindow;
    },
  },
});
