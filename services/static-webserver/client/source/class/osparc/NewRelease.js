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
    },

    /**
     * Always opens a popup with the NewRelease widget.
     * If the release link is a renderable markdown, it renders it.
     * Otherwise, shows the fallback intro text and link.
     */
    popUpReleaseNotes: function() {
      const newRelease = new osparc.NewRelease();
      const title = osparc.product.Utils.isProduct("osparc") ? qx.locale.Manager.tr("New Version Released") : qx.locale.Manager.tr("New Version of Osparc Platform Released");
      const colorManager = qx.theme.manager.Color.getInstance();
      const textColor = colorManager.resolve("text");
      const lightLogo = osparc.utils.Utils.getColorLuminance(textColor) > 0.4;
      const icon = lightLogo ? "osparc/osparc-o-white.svg" : "osparc/osparc-o-black.svg";
      const win = osparc.ui.window.Window.popUpInWindow(newRelease, title, 350, 135, icon).set({
        clickAwayClose: false,
        resizable: false,
        showClose: true
      });
      newRelease.addListener("releaseNotesLoaded", () => {
        const vpWidth = document.documentElement.clientWidth;
        const vpHeight = document.documentElement.clientHeight;
        const winWidth = Math.min(700, vpWidth - 50);
        const winHeight = Math.min(700, vpHeight - 50);
        const minHeight = Math.min(500, winHeight);
        win.set({
          width: winWidth,
          height: winHeight,
          minHeight,
          maxHeight: winHeight,
          resizable: true
        });
        win.moveTo(
          Math.round((vpWidth - winWidth) / 2),
          Math.round((vpHeight - winHeight) / 2)
        );
      });
      const closeBtn = win.getChildControl("close-button");
      osparc.utils.Utils.setIdToWidget(closeBtn, "newReleaseCloseBtn");
    },

    /**
     * Opens a dialog with rendered release notes markdown only if the
     * releaseLink points to a renderable GitHub markdown file.
     * @param {String} releaseLink The GitHub blob URL of the release notes.
     * @returns {Boolean} true if the dialog was opened, false otherwise.
     */
    openReleaseNotesDialog: function(releaseLink) {
      const rawUrl = osparc.NewRelease.toGitHubRawUrl(releaseLink);
      if (!rawUrl) {
        return false;
      }
      osparc.NewRelease.popUpReleaseNotes();
      return true;
    }
  },

  members: {
    __loadingLabel: null,

    __buildLayout: function() {
      const releaseLink = osparc.utils.Utils.getReleaseLink();
      const rawUrl = osparc.NewRelease.toGitHubRawUrl(releaseLink);

      if (rawUrl) {
        this.__addLoadingIndicator();
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
          this.__removeLoadingIndicator();
          this.__addMarkdown(markdown);
          this.__addDetailsLink(originalLink);
        })
        .catch(err => {
          console.warn("Could not fetch release notes from GitHub, falling back to link:", err);
          this.__removeLoadingIndicator();
          this.__addFallbackIntro();
          this.__addFallbackLink(originalLink);
        });
    },

    __addMarkdown: function(markdown) {
      // Load release-notes stylesheet
      const cssUri = qx.util.ResourceManager.getInstance().toUri("marked/release-notes.css");
      qx.module.Css.includeStylesheet(cssUri);

      // Inject CSS custom properties from the current theme so
      // release-notes.css works in both dark and light modes
      this.__applyThemeCssVars();

      const cleaned = this.__postProcessMarkdown(markdown);
      const mdWidget = new osparc.ui.markdown.Markdown(cleaned).set({
        padding: 10
      });
      // Apply release-notes CSS class for proper typography
      mdWidget.addListenerOnce("appear", () => {
        mdWidget.getContentElement().addClass("osparc-release-notes");
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
      // Strip the first top-level heading only if it says "Release Notes"
      let cleaned = markdown.replace(/^\s*#\s+Release Notes\s*\n*/, "");
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

    __addLoadingIndicator: function() {
      this.__loadingLabel = new qx.ui.basic.Atom().set({
        label: qx.locale.Manager.tr("Loading release notes..."),
        icon: "@FontAwesome5Solid/circle-notch/14",
        font: "text-14",
        alignX: "center",
        alignY: "middle"
      });
      this.__loadingLabel.getChildControl("icon").getContentElement().addClass("rotate");
      this._add(this.__loadingLabel);
    },

    __removeLoadingIndicator: function() {
      if (this.__loadingLabel) {
        this._remove(this.__loadingLabel);
        this.__loadingLabel.dispose();
        this.__loadingLabel = null;
      }
    },

    /**
     * Sets CSS custom properties (--rn-text-muted)
     * on the document root, resolved from the current qooxdoo theme colors.
     */
    __applyThemeCssVars: function() {
      const colorMgr = qx.theme.manager.Color.getInstance();
      const root = document.documentElement.style;
      root.setProperty("--rn-text-muted", colorMgr.resolve("text-opa70"));
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
        value: this.tr("What's New in oSparc ") + releaseTag,
        url: releaseLink,
        font: "link-label-14"
      });
      this._add(linkLabel);
    },
  }
});
