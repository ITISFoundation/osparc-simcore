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
    this.base(arguments, this.tr("About"));
    this.set({
      layout: new qx.ui.layout.VBox(5),
      contentPadding: 15,
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

  members: {
    __buildLayout: function() {
      this.add(new qx.ui.basic.Label(this.tr("oSPARC is powered by:")).set({
        font: "text-14"
      }));

      const tabView = new qx.ui.tabview.TabView().set({
        contentPadding: 5,
        contentPaddingTop: 10,
        barPosition: "top"
      });
      tabView.getChildControl("pane").setBackgroundColor("material-button-background");
      this.add(tabView, {
        flex: 1
      });

      const frontendPage = new qx.ui.tabview.Page(this.tr("Front-end")).set({
        layout: new qx.ui.layout.VBox(),
        backgroundColor: "material-button-background"
      });
      const backendPage = new qx.ui.tabview.Page(this.tr("Back-end")).set({
        layout: new qx.ui.layout.VBox(),
        backgroundColor: "material-button-background"
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
      this.__getBackendLibs().forEach(lib => {
        const entry = this.__createEntry(lib.name, lib.version, lib.url);
        page.add(entry);
      });
    },

    __createEntries: function(libs) {
      const entries = [];
      libs.forEach(lib => {
        entries.push(this.__createEntry(lib.name, lib.version, lib.url));
      });
      return entries;
    },

    __createEntry: function(item = "unknown-library", vers = "-", url) {
      let entryLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        marginBottom: 4
      });

      let entryLabel = null;
      if (url) {
        entryLabel = new osparc.ui.basic.LinkLabel(item, url);
      } else {
        entryLabel = new qx.ui.basic.Label(item);
      }
      entryLayout.set({
        font: "title-14"
      });
      entryLayout.add(entryLabel);

      let entryVersion = new qx.ui.basic.Label().set({
        value: vers,
        font: "text-14"
      });
      entryLayout.add(entryVersion);

      return entryLayout;
    },

    __getBackendLibs: function() {
      return [{
        name: "adminer",
        version: "4.8.0",
        url: "https://www.adminer.org/"
      }, {
        name: "postgres",
        version: "10.11",
        url: "https://www.postgresql.org/"
      }, {
        name: "flower",
        version: "0.9.5",
        url: "https://github.com/mher/flower"
      }, {
        name: "celery",
        version: "-",
        url: "https://docs.celeryproject.org/en/stable/"
      }, {
        name: "dask",
        version: "-",
        url: "https://docs.dask.org/en/latest/scheduler-overview.html"
      }, {
        name: "minio",
        version: "-",
        url: "https://min.io/"
      }, {
        name: "portainer",
        version: "-",
        url: "https://www.portainer.io/"
      }, {
        name: "redis",
        version: "-",
        url: "https://redis.io/"
      }, {
        name: "docker",
        version: "-",
        url: "https://www.docker.com/"
      }, {
        name: "docker registry",
        version: "-",
        url: "https://docs.docker.com/registry/"
      }];
    }
  }
});
