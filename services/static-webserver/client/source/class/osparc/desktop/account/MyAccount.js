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

qx.Class.define("osparc.desktop.account.MyAccount", {
  extend: osparc.ui.window.TabbedView,

  construct: function() {
    this.base(arguments);

    const miniProfile = osparc.desktop.account.MyAccount.createMiniProfileView().set({
      paddingRight: 10
    });
    this.addWidgetOnTopOfTheTabs(miniProfile);

    this.__profilePage = this.__addProfilePage();

    if (osparc.data.Permissions.getInstance().canDo("usage.all.read")) {
      this.__usagePage = this.__addUsagePage();
    }
  },

  statics: {
    createMiniProfileView: function(withSpacer = true) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(6)).set({
        alignX: "center",
        minWidth: 120,
        maxWidth: 150
      });

      const authData = osparc.auth.Data.getInstance();
      const username = authData.getUsername();
      const email = authData.getEmail();
      const avatarSize = 80;
      const img = new qx.ui.basic.Image().set({
        source: osparc.utils.Avatar.emailToThumbnail(email, username, avatarSize),
        maxWidth: avatarSize,
        maxHeight: avatarSize,
        scale: true,
        decorator: new qx.ui.decoration.Decorator().set({
          radius: avatarSize/2
        }),
        alignX: "center"
      });
      layout.add(img);

      const usernameLabel = new qx.ui.basic.Label().set({
        font: "text-14",
        alignX: "center"
      });
      authData.bind("username", usernameLabel, "value");
      layout.add(usernameLabel);

      const fullNameLabel = new qx.ui.basic.Label().set({
        font: "text-13",
        alignX: "center"
      });
      layout.add(fullNameLabel);
      authData.bind("firstName", fullNameLabel, "value", {
        converter: () => authData.getFullName()
      });
      authData.bind("lastName", fullNameLabel, "value", {
        converter: () => authData.getFullName()
      });

      if (authData.getRole() !== "user") {
        const role = authData.getFriendlyRole();
        const roleLabel = new qx.ui.basic.Label(role).set({
          font: "text-13",
          alignX: "center"
        });
        layout.add(roleLabel);
      }

      if (withSpacer) {
        layout.add(new qx.ui.core.Spacer(15, 15));
      }

      return layout;
    }
  },

  members: {
    __profilePage: null,
    __usagePage: null,

    __addProfilePage: function() {
      const title = this.tr("Profile");
      const iconSrc = "@FontAwesome5Solid/user/24";
      const profile = new osparc.desktop.account.ProfilePage();
      const page = this.addTab(title, iconSrc, profile);
      return page;
    },

    __addUsagePage: function() {
      const title = this.tr("Usage");
      const iconSrc = "@FontAwesome5Solid/list/22";
      const usageOverview = new osparc.desktop.credits.Usage();
      const page = this.addTab(title, iconSrc, usageOverview);
      return page;
    },

    openProfile: function() {
      this._openPage(this.__profilePage);
      return true;
    }
  }
});
