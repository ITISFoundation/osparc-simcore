/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.Dashboard", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments, new qx.ui.layout.HBox());

    qxapp.wrapper.JsonDiffPatch.getInstance().init();
    qxapp.wrapper.JsonTreeViewer.getInstance().init();

    let leftSpacer = new qx.ui.core.Spacer(60);
    let mainView = this.__createMainViewLayout();
    let rightSpacer = new qx.ui.core.Spacer(60);

    this.add(leftSpacer);
    this.add(mainView, {
      flex: 1
    });
    this.add(rightSpacer);
  },

  members: {
    __prjBrowser: null,
    __serviceBrowser: null,
    __dataManager: null,

    getPrjBrowser: function() {
      return this.__prjBrowser;
    },

    getServiceBrowser: function() {
      return this.__serviceBrowser;
    },

    getDataManager: function() {
      return this.__dataManager;
    },

    __createMainViewLayout: function() {
      let tabView = new qx.ui.tabview.TabView();

      [
        [this.tr("Studies"), this.__createStudiesView],
        [this.tr("Services"), this.__createServicesLayout],
        [this.tr("Data"), this.__createDataManagerLayout]
      ].forEach(tuple => {
        let tabPage = new qx.ui.tabview.Page(tuple[0]);
        tabPage.setLayout(new qx.ui.layout.VBox());

        let viewLayout = tuple[1].call(this);
        let scrollerMainView = new qx.ui.container.Scroll();
        scrollerMainView.add(viewLayout);
        tabPage.add(scrollerMainView, {
          flex: 1
        });

        tabView.add(tabPage);
      }, this);

      return tabView;
    },

    __createStudiesView: function() {
      let studiesView = this.__prjBrowser = new qxapp.desktop.PrjBrowser();
      return studiesView;
    },

    __createServicesLayout: function() {
      let servicesView = this.__serviceBrowser = new qxapp.desktop.ServiceBrowser();
      return servicesView;
    },

    __createDataManagerLayout: function() {
      let dataManagerView = this.__dataManager = new qxapp.desktop.DataManager();
      return dataManagerView;
    }
  }
});
