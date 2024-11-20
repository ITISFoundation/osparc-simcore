/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.preferences.Preferences", {
  extend: osparc.ui.window.TabbedView,

  construct: function() {
    this.base(arguments);

    this.__addGeneralSettings();
    this.__addConfirmationSettings();
    if (osparc.product.Utils.showPreferencesTokens()) {
      this.__addTokensPage();
    }
    if (osparc.data.Permissions.getInstance().canDo("user.tag")) {
      this.__addTagsPage();
    }
    if (osparc.product.Utils.showClusters()) {
      this.__addClustersPage();
    }
  },

  members: {
    __addGeneralSettings: function() {
      const title = this.tr("General Settings");
      const iconSrc = "@FontAwesome5Solid/cogs/24";
      const generalPage = new osparc.desktop.preferences.pages.GeneralPage();
      this.addTab(title, iconSrc, generalPage);
    },

    __addConfirmationSettings: function() {
      const title = this.tr("Confirmation Settings");
      const iconSrc = "@FontAwesome5Solid/question-circle/24";
      const confirmPage = new osparc.desktop.preferences.pages.ConfirmationsPage();
      this.addTab(title, iconSrc, confirmPage);
    },

    __addTokensPage: function() {
      const title = this.tr("API Keys/Tokens");
      const iconSrc = "@FontAwesome5Solid/exchange-alt/24";
      const tokensPage = new osparc.desktop.preferences.pages.TokensPage();
      this.addTab(title, iconSrc, tokensPage);
    },

    __addTagsPage: function() {
      const title = this.tr("Create/Edit Tags");
      const iconSrc = "@FontAwesome5Solid/tags/24";
      const tagsPage = new osparc.desktop.preferences.pages.TagsPage();
      const page = this.addTab(title, iconSrc, tagsPage);
      osparc.utils.Utils.setIdToWidget(page.getChildControl("button"), "preferencesTagsTabBtn");
    },

    __addClustersPage: function() {
      const title = this.tr("Clusters");
      const iconSrc = "@FontAwesome5Solid/server/24";
      const clustersPage = new osparc.desktop.preferences.pages.ClustersPage();
      const page = this.addTab(title, iconSrc, clustersPage);
      const clustersBtn = page.getChildControl("button");
      clustersBtn.exclude();
      const isDisabled = osparc.utils.DisabledPlugins.isClustersDisabled();
      if (isDisabled === false) {
        osparc.data.Resources.get("clusters")
          .then(clusters => {
            if (clusters.length || osparc.data.Permissions.getInstance().canDo("user.clusters.create")) {
              clustersBtn.show();
            }
          })
          .catch(err => console.error(err));
      }
    },
  }
});
