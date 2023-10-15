/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/** Application's preferences
 *
 *  - multi-page modal window
 *
*/

qx.Class.define("osparc.desktop.preferences.PreferencesWindow", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    this.base(arguments, "preferences", this.tr("Preferences"));
    this.set({
      layout: new qx.ui.layout.Grow(),
      modal: true,
      width: 550,
      height: 660,
      showMaximize: false,
      showMinimize: false,
      resizable: false,
      appearance: "service-window"
    });
    const closeBtn = this.getChildControl("close-button");
    osparc.utils.Utils.setIdToWidget(closeBtn, "preferencesWindowCloseBtn");

    const tabView = new qx.ui.tabview.TabView().set({
      barPosition: "left",
      contentPadding: 0
    });

    const confirmPage = new osparc.desktop.preferences.pages.ConfirmationsPage();
    tabView.add(confirmPage);

    if (osparc.product.Utils.showPreferencesTokens()) {
      const tokensPage = new osparc.desktop.preferences.pages.TokensPage();
      const tokensBtn = tokensPage.getChildControl("button");
      osparc.utils.Utils.setIdToWidget(tokensBtn, "preferencesTokensTabBtn");
      tabView.add(tokensPage);
    }

    if (osparc.data.Permissions.getInstance().canDo("user.tag")) {
      const tagsPage = new osparc.desktop.preferences.pages.TagsPage();
      osparc.utils.Utils.setIdToWidget(tagsPage.getChildControl("button"), "preferencesTagsTabBtn");
      tabView.add(tagsPage);
    }

    if (osparc.product.Utils.showClusters()) {
      const clustersPage = new osparc.desktop.preferences.pages.ClustersPage();
      const clustersBtn = clustersPage.getChildControl("button");
      osparc.utils.Utils.setIdToWidget(clustersBtn, "preferencesClustersTabBtn");
      tabView.add(clustersPage);
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
    }

    if (osparc.data.Permissions.getInstance().canDo("statics.read")) {
      const testerPage = new osparc.desktop.preferences.pages.TesterPage();
      tabView.add(testerPage);
    }

    this.add(tabView);
  },

  statics: {
    openWindow: function() {
      const preferencesWindow = new osparc.desktop.preferences.PreferencesWindow();
      preferencesWindow.center();
      preferencesWindow.open();
      return preferencesWindow;
    }
  }
});
