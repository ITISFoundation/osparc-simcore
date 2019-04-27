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
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    qxapp.wrapper.JsonDiffPatch.getInstance().init();
    qxapp.wrapper.JsonTreeViewer.getInstance().init();

    let leftSpacer = new qx.ui.core.Spacer(60);
    let mainView = this.__createMainViewLayout();
    let rightSpacer = new qx.ui.core.Spacer(60);

    this._add(leftSpacer);
    this._add(mainView, {
      flex: 1
    });
    this._add(rightSpacer);
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
      let studiesView = this.__prjBrowser = new qxapp.desktop.StudyBrowser();
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
