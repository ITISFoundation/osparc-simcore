/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Pedro Crespo (pcrespov)

************************************************************************ */

qx.Class.define("osparc.About", {
  extend: osparc.ui.window.Window,
  type: "singleton",

  construct: function() {
    this.base(arguments, this.tr("About oSPARC"));
    this.set({
      layout: new qx.ui.layout.VBox(5),
      maxWidth: this.self().MAX_WIDTH,
      contentPadding: this.self().PADDING,
      showMaximize: false,
      showMinimize: false,
      resizable: false,
      centerOnAppear: true,
      clickAwayClose: true,
      modal: true
    });
    const closeBtn = this.getChildControl("close-button");
    osparc.utils.Utils.setIdToWidget(closeBtn, "aboutWindowCloseBtn");

    this.__buildLayout();
  },

  statics: {
    MAX_WIDTH: 320,
    PADDING: 15
  },

  members: {
    __buildLayout: function() {
      const introText = new qx.ui.basic.Label().set({
        font: "text-14",
        maxWidth: this.self().MAX_WIDTH - 2*this.self().PADDING,
        rich: true,
        wrap: true
      });
      this.add(introText);
      const aboutText = this.tr("oSPARC is built upon a number of open-source \
      resources - we can't do it all alone! Some of the technologies that we leverage include:");
      introText.setValue(aboutText);

      const tabView = new qx.ui.tabview.TabView().set({
        contentPaddingTop: 10,
        contentPaddingLeft: 0,
        barPosition: "top"
      });
      tabView.getChildControl("pane").setBackgroundColor("background-main-2");
      this.add(tabView, {
        flex: 1
      });

      const frontendPage = new qx.ui.tabview.Page(this.tr("Front-end")).set({
        layout: new qx.ui.layout.VBox(5),
        backgroundColor: "background-main-2"
      });
      const backendPage = new qx.ui.tabview.Page(this.tr("Back-end")).set({
        layout: new qx.ui.layout.VBox(5),
        backgroundColor: "background-main-2"
      });
      tabView.add(frontendPage);
      tabView.add(backendPage);
      this.__populateFrontendEntries(frontendPage);
      this.__populateBackendEntries(backendPage);
    },

    __populateFrontendEntries: function(page) {
      [
        this.__createEntries([osparc.utils.LibVersions.getPlatformVersion()]),
        this.__createEntries([osparc.utils.LibVersions.getUIVersion()]),
        [new qx.ui.core.Spacer(null, 10)],
        this.__createEntries([osparc.utils.LibVersions.getQxCompiler()]),
        this.__createEntries(osparc.utils.LibVersions.getQxLibraryInfoMap()),
        [new qx.ui.core.Spacer(null, 10)],
        this.__createEntries(osparc.utils.LibVersions.get3rdPartyLibs())
      ].forEach(entries => {
        entries.forEach(entry => {
          page.add(entry);
        });
      });
    },

    __populateBackendEntries: function(page) {
      osparc.utils.LibVersions.getBackendLibs()
        .then(libs => {
          libs.forEach(lib => {
            const entry = this.__createEntry(lib);
            page.add(entry);
          });
        });
    },

    __createEntries: function(libs) {
      const entries = [];
      libs.forEach(lib => {
        entries.push(this.__createEntry(lib));
      });
      return entries;
    },

    __createEntry: function(lib) {
      const label = lib.name || "unknown-library";
      const version = lib.version || "-";
      const url = lib.url || null;
      const thumbnail = lib.thumbnail || null;

      if (thumbnail) {
        const image = new qx.ui.basic.Image(thumbnail).set({
          height: 30,
          maxWidth: this.self().MAX_WIDTH - 2*this.self().PADDING,
          scale: true,
          toolTipText: label + (version === "-" ? "" : (" " + version))
        });
        image.getContentElement().setStyles({
          "object-fit": "contain",
          "object-position": "left"
        });
        if (url) {
          image.set({
            cursor: "pointer"
          });
          image.addListener("tap", () => window.open(url));
        }
        return image;
      }

      const entryLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      let entryLabel = null;
      if (url) {
        entryLabel = new osparc.ui.basic.LinkLabel(label, url);
      } else {
        entryLabel = new qx.ui.basic.Label(label);
      }
      entryLayout.set({
        font: "title-14"
      });
      entryLayout.add(entryLabel);

      let entryVersion = new qx.ui.basic.Label().set({
        value: version,
        font: "text-14"
      });
      entryLayout.add(entryVersion);
      return entryLayout;
    }
  }
});
