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

qx.Class.define("osparc.LogoutWindow", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    this.base(arguments, "too-small-logout", this.tr("Window too small"));

    this.set({
      layout: new qx.ui.layout.VBox(10),
      contentPadding: 15,
      modal: true,
      showMaximize: false,
      showMinimize: false,
    });

    this.__buildLayout();
  },

  statics: {
    openWindow: function() {
      const orgsWindow = new osparc.LogoutWindow();
      orgsWindow.center();
      orgsWindow.open();
      return orgsWindow;
    }
  },

  members: {
    __buildLayout: function() {
      const message = this.__createMessage();
      this.add(message);

      const logoutButton = this.__createLogoutButton();
      this.add(logoutButton);
    },

    __createMessage: function() {
      const introText = this.tr("The application can't perform in such a small window.");
      const introLabel = new qx.ui.basic.Label(introText);
      return introLabel;
    },

    __createLogoutButton: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignX: "right"
      }));

      const authData = osparc.auth.Data.getInstance();
      const button = new qx.ui.form.Button(authData.isGuest() ? this.tr("Exit") : this.tr("Log out")).set({
        allowGrowX: false
      });
      button.addListener("execute", () => qx.core.Init.getApplication().logout());
      layout.add(button);

      const isLoggedIn = osparc.auth.Manager.getInstance().isLoggedIn();
      layout.setVisibility(isLoggedIn ? "visible" : "excluded");

      return layout;
    },
  }
});
