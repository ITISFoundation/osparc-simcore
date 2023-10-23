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

qx.Class.define("osparc.desktop.credits.MyAccount", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      padding: 20,
      paddingLeft: 10
    });

    const tabViews = this.__tabsView = new qx.ui.tabview.TabView().set({
      barPosition: "left",
      contentPadding: 0
    });
    tabViews.getChildControl("bar").add(this.self().createMiniProfileView());

    const profilePage = this.__profilePage = this.__getProfilePage();
    tabViews.add(profilePage);

    if (osparc.data.Permissions.getInstance().canDo("usage.all.read")) {
      const usagePage = this.__usagePage = this.__getUsagePage();
      tabViews.add(usagePage);
    }

    this._add(tabViews);
  },

  statics: {
    createMiniProfileView: function(withSpacer = true) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(6)).set({
        alignX: "center",
        minWidth: 120,
        maxWidth: 150,
        paddingRight: 10
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
    __tabsView: null,
    __profilePage: null,
    __usagePage: null,

    __getProfilePage: function() {
      const page = new osparc.desktop.credits.ProfilePage();
      page.showLabelOnTab();
      return page;
    },

    __getUsagePage: function() {
      const title = this.tr("Usage");
      const iconSrc = "@FontAwesome5Solid/list/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const usageOverview = new osparc.desktop.credits.Usage();
      usageOverview.set({
        margin: 10
      });
      page.add(usageOverview);
      return page;
    },

    __openPage: function(page) {
      if (page) {
        this.__tabsView.setSelection([page]);
        return true;
      }
      return false;
    },

    openProfile: function() {
      this.__openPage(this.__profilePage);
      return true;
    }
  }
});
