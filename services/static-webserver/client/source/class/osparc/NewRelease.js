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

qx.Class.define("osparc.NewRelease", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__buildLayout();
  },

  statics: {
    /**
     * Compare the version logged in the cache and the one being shown
     */
    firstTimeISeeThisFrontend: function() {
      let isIt = false;
      const lastUICommit = osparc.utils.Utils.localCache.getLastCommitVcsRefUI();
      const thisUICommit = osparc.utils.LibVersions.getVcsRefUI();
      if (lastUICommit && thisUICommit) {
        isIt = lastUICommit !== thisUICommit;
      }
      osparc.utils.Utils.localCache.setLastCommitVcsRefUI(thisUICommit);
      return isIt;
    },

    /**
     * Compare the latest version provided by the backend with the one loaded in the browser (might be an old cached one)
     */
    isMyFrontendOld: async function() {
      const lastUICommit = await osparc.store.AppSummary.getInstance().getLatestUIFromBE();
      const thisUICommit = osparc.utils.LibVersions.getVcsRefUI();
      if (lastUICommit && thisUICommit) {
        return lastUICommit !== thisUICommit;
      }
      return false;
    },

    getText: function() {
      return qx.locale.Manager.tr("We are pleased to announce that some new features were deployed for you!");
    }
  },

  members: {
    __buildLayout: function() {
      const introText = this.self().getText();
      const introLabel = new qx.ui.basic.Label(introText).set({
        rich: true,
        wrap: true
      });
      this._add(introLabel);

      const detailsText = this.tr("What's new");
      // old commit link
      const link = osparc.utils.LibVersions.getVcsRefUrl();
      const linkLabel = new osparc.ui.basic.LinkLabel(detailsText, link);
      this._add(linkLabel);
      const rData = osparc.store.StaticInfo.getInstance().getReleaseData();
      if (rData) {
        const releaseUrl = rData["url"];
        if (releaseUrl) {
          linkLabel.setUrl(releaseUrl);
        }
      }
    }
  }
});
