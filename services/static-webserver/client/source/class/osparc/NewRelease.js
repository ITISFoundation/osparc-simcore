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

/**
 * @asset(marked/release-notes.css)
 */

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
      // const releaseLink = osparc.utils.Utils.getReleaseLink();
      // testing
      const releaseLink = "https://github.com/ITISFoundation/osparc-issues/blob/master/release-notes/osparc/v1.89.0.md";
      const rawUrl = osparc.NewRelease.toGitHubRawUrl(releaseLink);

      if (rawUrl) {
        this.__fetchAndRenderMarkdown(rawUrl, releaseLink);
      } else {
        this.__addFallbackIntro();
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
          this.__addMarkdown(markdown);
          this.__addDetailsLink(originalLink);
        })
        .catch(err => {
          console.warn("Could not fetch release notes from GitHub, falling back to link:", err);
          this.__addFallbackIntro();
          this.__addFallbackLink(originalLink);
        });
    },

    __addMarkdown: function(markdown) {
      // Load release-notes stylesheet
      const cssUri = qx.util.ResourceManager.getInstance().toUri("marked/release-notes.css");
      qx.module.Css.includeStylesheet(cssUri);

      const cleaned = this.__postProcessMarkdown(markdown);
      const mdWidget = new osparc.ui.markdown.Markdown(cleaned).set({
        padding: 10
      });
      // Apply release-notes CSS class for proper typography
      mdWidget.addListenerOnce("appear", () => {
        mdWidget.getContentElement().addClass("osparc-release-notes");
      });
      mdWidget.addListener("resized", () => {
        this.__styleMarkdownImages(mdWidget);
      });
      const scrollContainer = new qx.ui.container.Scroll();
      scrollContainer.add(mdWidget);
      this._add(scrollContainer, {
        flex: 1
      });
      this.fireEvent("releaseNotesLoaded");
    },

    /**
     * Post-processes fetched markdown before rendering:
     * - Strips the first top-level heading (e.g. "# Release Notes")
     * - Collapses multi-line HTML tags into single lines so that
     *   marked's `breaks: true` option doesn't corrupt them with <br> tags.
     */
    __postProcessMarkdown: function(markdown) {
      // Strip the first top-level heading if present
      let cleaned = markdown.replace(/^\s*#\s+.*\n*/, "");
      // Iteratively collapse multi-line HTML tags into single lines.
      // marked's `breaks: true` inserts <br> at every newline, which corrupts
      // multi-line HTML tags like <img height="800"\nalt="..."\nsrc="...">.
      // Each pass collapses one newline per tag; repeat until stable.
      let prev;
      do {
        prev = cleaned;
        cleaned = cleaned.replace(/<([a-zA-Z][^>\n]*)\n\s*/g, "<$1 ");
      } while (cleaned !== prev);
      return cleaned;
    },

    /**
     * Applies max-width style to all images inside the Markdown widget.
     * Called on every resize so newly loaded images are also styled.
     */
    __styleMarkdownImages: function(mdWidget) {
      const el = mdWidget.getContentElement().getDomElement();
      if (el) {
        const images = qx.bom.Selector.query("img", el);
        for (let i = 0; i < images.length; i++) {
          images[i].style.maxWidth = "100%";
          images[i].style.height = "auto";
        }
      }
    },

    __addDetailsLink: function(releaseLink) {
      const releaseTag = osparc.utils.Utils.getReleaseTag();
      const linkLabel = new osparc.ui.basic.LinkLabel().set({
        value: this.tr("Check more details in ") + releaseTag,
        url: releaseLink,
        font: "link-label-14",
        paddingLeft: 10,
      });
      this._add(linkLabel);
    },

    __addFallbackIntro: function() {
      const introText = qx.locale.Manager.tr("We are pleased to announce that some new features were deployed for you!");
      const introLabel = new qx.ui.basic.Label(introText).set({
        font: "text-14",
        rich: true,
        wrap: true
      });
      this._add(introLabel);
    },

    __addFallbackLink: function(releaseLink) {
      const releaseTag = osparc.utils.Utils.getReleaseTag();
      const linkLabel = new osparc.ui.basic.LinkLabel().set({
        value: this.tr("What's New in ") + releaseTag,
        url: releaseLink,
        font: "link-label-14"
      });
      this._add(linkLabel);
    },
  }
});
