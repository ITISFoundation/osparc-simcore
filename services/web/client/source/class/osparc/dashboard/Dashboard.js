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
 * - Explorer
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
      contentPaddingTop: 15,
      contentPaddingLeft: 0,
      barPosition: "top"
    });

    osparc.wrapper.Svg.getInstance().init();
    osparc.wrapper.JsonDiffPatch.getInstance().init();
    osparc.wrapper.JsonTreeViewer.getInstance().init();
    osparc.wrapper.DOMPurify.getInstance().init();
    osparc.wrapper.RadialMenu.getInstance().init()
      .then(loaded => {
        if (loaded) {
          // hack to trigger the fonts loading
          const menu = osparc.wrapper.RadialMenu.getInstance().createMenu();
          menu.show();
          menu.hide();
        }
      });
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
      const tabs = [{
        label: this.tr("Studies"),
        buildLayout: this.__createStudyBrowser
      }, {
        label: this.tr("Discover"),
        buildLayout: this.__createExploreBrowser
      }];
      if (!osparc.utils.Utils.isProduct("s4l")) {
        tabs.push({
          label: this.tr("Data"),
          buildLayout: this.__createDataBrowser}
        );
      }
      tabs.forEach(({label, buildLayout}) => {
        const tabPage = new qx.ui.tabview.Page(label).set({
          appearance: "dashboard-page"
        });
        const tabButton = tabPage.getChildControl("button");
        tabButton.set({
          font: "text-16",
          minWidth: 70
        });
        const id = label.getMessageId().toLowerCase() + "TabBtn";
        osparc.utils.Utils.setIdToWidget(tabButton, id);
        tabPage.setLayout(new qx.ui.layout.Grow());

        const viewLayout = buildLayout.call(this);
        tabButton.addListener("execute", () => {
          if (viewLayout.resetSelection) {
            viewLayout.resetSelection();
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
