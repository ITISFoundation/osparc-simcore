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

/**
 * Widget containing a TabView including:
 * - StudyBrowser
 * - ServiceBrowser
 * - DataManager
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let dashboard = new qxapp.desktop.Dashboard();
 *   this.getRoot().add(dashboard);
 * </pre>
 */

qx.Class.define("qxapp.desktop.Dashboard", {
  extend: qx.ui.tabview.TabView,

  construct: function(studyId) {
    this.base(arguments);

    this.setBarPosition("left");

    qxapp.wrapper.JsonDiffPatch.getInstance().init();
    qxapp.wrapper.JsonTreeViewer.getInstance().init();
    this.__createMainViewLayout(studyId);
  },

  properties: {
    appearance: {
      init: "dashboard",
      refine: true
    }
  },

  members: {
    __prjBrowser: null,
    __serviceBrowser: null,
    __dataManager: null,

    getStudyBrowser: function() {
      return this.__prjBrowser;
    },

    getServiceBrowser: function() {
      return this.__serviceBrowser;
    },

    getDataManager: function() {
      return this.__dataManager;
    },

    __createMainViewLayout: function(studyId) {
      [
        [this.tr("Studies"), this.__createStudiesView],
        [this.tr("Services"), this.__createServicesLayout],
        [this.tr("Data"), this.__createDataManagerLayout]
      ].forEach(tuple => {
        const tabPage = new qx.ui.tabview.Page(tuple[0]).set({
          appearance: "dashboard-page"
        });
        const id = tuple[0].getMessageId().toLowerCase() + "TabBtn";
        qxapp.utils.Utils.setIdToWidget(tabPage.getChildControl("button"), id);
        tabPage.setLayout(new qx.ui.layout.Grow());

        const viewLayout = tuple[1].call(this, studyId);
        const scrollerMainView = new qx.ui.container.Scroll();
        scrollerMainView.add(viewLayout);
        tabPage.add(scrollerMainView);

        this.add(tabPage);
      }, this);
    },

    __createStudiesView: function(studyId) {
      const studiesView = this.__prjBrowser = new qxapp.desktop.StudyBrowser(studyId);
      return studiesView;
    },

    __createServicesLayout: function() {
      const servicesView = this.__serviceBrowser = new qxapp.desktop.ServiceBrowser();
      return servicesView;
    },

    __createDataManagerLayout: function() {
      const dataManagerView = this.__dataManager = new qxapp.desktop.DataManager();
      return dataManagerView;
    }
  }
});
