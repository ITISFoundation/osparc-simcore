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
     * Compare the version logged in the cache with the one being shown
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
    isMyFrontendOld: function() {
      return new Promise((resolve, reject) => {
        osparc.store.AppSummary.getLatestUIFromBE()
          .then(lastUICommit => {
            const thisUICommit = osparc.utils.LibVersions.getVcsRefUI();
            if (lastUICommit && thisUICommit) {
              resolve(lastUICommit !== thisUICommit)
            } else {
              reject();
            }
          })
          .catch(() => reject());
      });
    }
  },

  members: {
    __buildLayout: function() {
      const introText = qx.locale.Manager.tr("We are pleased to announce that some new features were deployed for you!");
      const introLabel = new qx.ui.basic.Label(introText).set({
        font: "text-14",
        rich: true,
        wrap: true
      });
      this._add(introLabel);

      const rData = osparc.store.StaticInfo.getInstance().getReleaseData();
      const url = rData["url"] || osparc.utils.LibVersions.getVcsRefUrl();
      const linkLabel = new osparc.ui.basic.LinkLabel().set({
        value: this.tr("What's new"),
        url,
        font: "link-label-14"
      });
      this._add(linkLabel);
    }
  }
});
