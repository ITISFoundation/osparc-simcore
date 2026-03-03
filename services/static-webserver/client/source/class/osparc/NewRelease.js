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

  events: {
    /** Fired when embedded release notes are successfully loaded */
    "releaseNotesLoaded": "qx.event.type.Event"
  },

  statics: {
    /**
     * Compare the version logged in the cache with the one being shown
     */
    firstTimeISeeThisFrontend: function() {
      // testing
      return true;
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
    },

    /**
     * Converts a GitHub blob URL to the corresponding raw.githubusercontent.com URL.
     * Returns null if the URL is not a recognized GitHub markdown blob URL.
     * @param {String} url
     * @returns {String|null}
     */
    toGitHubRawUrl: function(url) {
      if (!url) {
        return null;
      }
      // Match: https://github.com/{owner}/{repo}/blob/{branch}/{path}.md
      const match = url.match(/^https:\/\/github\.com\/([^/]+)\/([^/]+)\/blob\/(.+\.md)$/);
      if (match) {
        const owner = match[1];
        const repo = match[2];
        const branchAndPath = match[3];
        return `https://raw.githubusercontent.com/${owner}/${repo}/${branchAndPath}`;
      }
      return null;
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

      // const releaseLink = osparc.utils.Utils.getReleaseLink();
      // testing
      const releaseLink = "https://github.com/ITISFoundation/osparc-issues/blob/master/release-notes/s4l/v1.88.0.md";
      const rawUrl = osparc.NewRelease.toGitHubRawUrl(releaseLink);

      if (rawUrl) {
        this.__fetchAndRenderMarkdown(rawUrl, releaseLink);
      } else {
        this.__addFallbackLink(releaseLink);
      }
    },

    __fetchAndRenderMarkdown: function(rawUrl, originalLink) {
      fetch(rawUrl)
        .then(response => {
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }
          return response.text();
        })
        .then(markdown => {
          const mdWidget = new osparc.ui.markdown.Markdown(markdown);
          const scrollContainer = new qx.ui.container.Scroll();
          scrollContainer.add(mdWidget);
          this._add(scrollContainer, {
            flex: 1
          });
          this.fireEvent("releaseNotesLoaded");
        })
        .catch(err => {
          console.warn("Could not fetch release notes from GitHub, falling back to link:", err);
          this.__addFallbackLink(originalLink);
        });
    },

    __addFallbackLink: function(releaseLink) {
      const releaseTag = osparc.utils.Utils.getReleaseTag();
      const linkLabel = new osparc.ui.basic.LinkLabel().set({
        value: this.tr("What's New in ") + releaseTag,
        url: releaseLink,
        font: "link-label-14"
      });
      this._add(linkLabel);
    }
  }
});
