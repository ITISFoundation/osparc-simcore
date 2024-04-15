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
      const email = authData.getEmail();
      const avatarSize = 80;
      const img = new qx.ui.basic.Image().set({
        source: osparc.utils.Avatar.getUrl(email, avatarSize),
        maxWidth: avatarSize,
        maxHeight: avatarSize,
        scale: true,
        decorator: new qx.ui.decoration.Decorator().set({
          radius: avatarSize/2
        }),
        alignX: "center"
      });
      layout.add(img);

      const name = new qx.ui.basic.Label().set({
        font: "text-14",
        alignX: "center"
      });
      layout.add(name);
      authData.bind("firstName", name, "value", {
        converter: firstName => firstName + " " + authData.getLastName()
      });
      authData.bind("lastName", name, "value", {
        converter: lastName => authData.getFirstName() + " " + lastName
      });

      const role = authData.getFriendlyRole();
      const roleLabel = new qx.ui.basic.Label(role).set({
        font: "text-13",
        alignX: "center"
      });
      layout.add(roleLabel);

      const emailLabel = new qx.ui.basic.Label(email).set({
        font: "text-13",
        alignX: "center"
      });
      layout.add(emailLabel);

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
