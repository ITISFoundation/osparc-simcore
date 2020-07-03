/* ************************************************************************

   osparc - the simcore frontend

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
 *   let dashboard = new osparc.dashboard.Dashboard();
 *   this.getRoot().add(dashboard);
 * </pre>
 */

qx.Class.define("osparc.dashboard.Dashboard", {
  extend: qx.ui.tabview.TabView,

  construct: function() {
    this.base(arguments);

    this.set({
      contentPaddingLeft: 0,
      barPosition: "top"
    });

    osparc.wrapper.JsonDiffPatch.getInstance().init();
    osparc.wrapper.JsonTreeViewer.getInstance().init();
    osparc.wrapper.DOMPurify.getInstance().init();
    this.__createMainViewLayout();
  },

  properties: {
    appearance: {
      init: "dashboard",
      refine: true
    }
  },

  members: {
    __studyBrowser: null,
    __exploreBrowser: null,

    getStudyBrowser: function() {
      return this.__studyBrowser;
    },

    getExploreBrowser: function() {
      return this.__exploreBrowser;
    },

    __createMainViewLayout: function() {
      [
        [this.tr("Studies"), this.__createStudyBrowser],
        // [this.tr("Services"), this.__createServiceBrowser],
        [this.tr("Data"), this.__createDataBrowser],
        [this.tr("Discover"), this.__createExploreBrowser]
      ].forEach(tuple => {
        const tabPage = new qx.ui.tabview.Page(tuple[0]).set({
          appearance: "dashboard-page"
        });
        const tabButton = tabPage.getChildControl("button");
        tabButton.setFont("text-16");
        const id = tuple[0].getMessageId().toLowerCase() + "TabBtn";
        osparc.utils.Utils.setIdToWidget(tabButton, id);
        tabPage.setLayout(new qx.ui.layout.Grow());

        const viewLayout = tuple[1].call(this);
        tabButton.addListener("execute", () => {
          if (viewLayout.resetSelection) {
            viewLayout.resetSelection();
          }
          if (viewLayout.resetFilter) {
            viewLayout.resetFilter();
          }
        }, this);
        const scrollerMainView = new qx.ui.container.Scroll();
        scrollerMainView.add(viewLayout);
        tabPage.add(scrollerMainView);

        this.add(tabPage);
      }, this);
    },

    __createStudyBrowser: function() {
      const studiesView = this.__studyBrowser = new osparc.dashboard.StudyBrowser();
      return studiesView;
    },

    __createDataBrowser: function() {
      const dataManagerView = new osparc.dashboard.DataBrowser();
      return dataManagerView;
    },

    __createExploreBrowser: function() {
      const exploreView = this.__exploreBrowser = new osparc.dashboard.ExploreBrowser();
      return exploreView;
    }
  }
});
