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

qx.Class.define("osparc.TooSmallDialog", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    this.base(arguments, "too-small-logout", this.tr("Window size too small"));

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
      const orgsWindow = new osparc.TooSmallDialog();
      orgsWindow.center();
      orgsWindow.open();
      return orgsWindow;
    }
  },

  members: {
    __buildLayout: function() {
      const message = this.__createMessage();
      this.add(message);

      // if the user is logged in, let them log out, the user menu might be unreachable
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

      const button = new qx.ui.form.Button().set({
        allowGrowX: false
      });
      button.addListener("execute", () => qx.core.Init.getApplication().logout());
      layout.add(button);

      const authData = osparc.auth.Data.getInstance();
      authData.bind("loggedIn", layout, "visibility", {
        converter: isLoggedIn => isLoggedIn ? "visible" : "excluded"
      });
      authData.bind("guest", button, "label", {
        converter: isGuest => isGuest ? this.tr("Exit") : this.tr("Log out")
      });

      return layout;
    },
  }
});
