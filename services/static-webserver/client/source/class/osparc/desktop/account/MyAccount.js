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
    this.addWidgetToTabs(miniProfile);

    this.__profilePage = this.__addProfilePage();

    // show Usage in My Account if wallets are not enabled. If they are enabled it will be in the BIlling Center
    if (!osparc.store.StaticInfo.isBillableProduct()) {
      if (osparc.data.Permissions.getInstance().canDo("usage.all.read")) {
        this.__usagePage = this.__addUsagePage();
      }
    }

    this.__addGeneralSettings();
    this.__addConfirmationSettings();
    if (osparc.product.Utils.showPreferencesTokens()) {
      this.__addTokensPage();
    }
    if (osparc.data.Permissions.getInstance().canDo("user.tag")) {
      this.__addTagsPage();
    }
  },

  statics: {
    createMiniProfileView: function(userData) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(6)).set({
        alignX: "center",
        minWidth: 120,
        maxWidth: 150
      });

      if (!userData) {
        userData = osparc.auth.Data.getInstance();
      }
      const userName = userData.getUserName();
      const email = userData.getEmail();
      const avatarSize = 80;
      const img = new qx.ui.basic.Image().set({
        source: osparc.utils.Avatar.emailToThumbnail(email, userName, avatarSize),
        maxWidth: avatarSize,
        maxHeight: avatarSize,
        scale: true,
        decorator: new qx.ui.decoration.Decorator().set({
          radius: avatarSize/2
        }),
        alignX: "center"
      });
      layout.add(img);

      const userNameLabel = new qx.ui.basic.Label().set({
        font: "text-14",
        alignX: "center"
      });
      userData.bind("userName", userNameLabel, "value");
      layout.add(userNameLabel);

      const fullNameLabel = new qx.ui.basic.Label().set({
        font: "text-13",
        alignX: "center"
      });
      layout.add(fullNameLabel);
      userData.bind("firstName", fullNameLabel, "value", {
        converter: () => userData.getFullName()
      });
      userData.bind("lastName", fullNameLabel, "value", {
        converter: () => userData.getFullName()
      });

      if (userData.getRole() !== "user") {
        const role = userData.getFriendlyRole();
        const roleLabel = new qx.ui.basic.Label(role).set({
          font: "text-13",
          alignX: "center"
        });
        layout.add(roleLabel);
      }

      layout.add(new qx.ui.core.Spacer(15, 15));

      return layout;
    }
  },

  members: {
    __profilePage: null,
    __usagePage: null,
    __tagsPage: null,

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
    __addGeneralSettings: function() {
      const title = this.tr("Settings");
      const iconSrc = "@FontAwesome5Solid/cogs/22";
      const generalPage = new osparc.desktop.preferences.pages.GeneralPage();
      this.addTab(title, iconSrc, generalPage);
    },

    __addConfirmationSettings: function() {
      const title = this.tr("Confirmations");
      const iconSrc = "@FontAwesome5Solid/question-circle/22";
      const confirmPage = new osparc.desktop.preferences.pages.ConfirmationsPage();
      this.addTab(title, iconSrc, confirmPage);
    },

    __addTokensPage: function() {
      const title = this.tr("API Keys/Tokens");
      const iconSrc = "@FontAwesome5Solid/exchange-alt/22";
      const tokensPage = new osparc.desktop.preferences.pages.TokensPage();
      this.addTab(title, iconSrc, tokensPage);
    },

    __addTagsPage: function() {
      const title = this.tr("Create/Edit Tags");
      const iconSrc = "@FontAwesome5Solid/tags/22";
      const tagsPage = new osparc.desktop.preferences.pages.TagsPage();
      const page = this.__tagsPage = this.addTab(title, iconSrc, tagsPage);
      osparc.utils.Utils.setIdToWidget(page.getChildControl("button"), "preferencesTagsTabBtn");
    },

    openTags: function() {
      if (this.__tagsPage) {
        this._openPage(this.__tagsPage);
      }
    },
  }
});
