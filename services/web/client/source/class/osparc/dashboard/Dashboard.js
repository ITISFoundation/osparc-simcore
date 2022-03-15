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
    __templateBrowser: null,
    __serviceBrowser: null,
    __dataBrowser: null,

    getStudyBrowser: function() {
      return this.__studyBrowser;
    },

    getTemplateBrowser: function() {
      return this.__templateBrowser;
    },

    getServiceBrowser: function() {
      return this.__serviceBrowser;
    },

    __createMainViewLayout: function() {
      const tabs = [{
        label: this.tr("STUDIES"),
        buildLayout: this.__createStudyBrowser
      }, {
        label: this.tr("TEMPLATES"),
        buildLayout: this.__createTemplateBrowser
      }, {
        label: this.tr("SERVICES"),
        buildLayout: this.__createServiceBrowser
      }];
      if (!osparc.utils.Utils.isProduct("s4l")) {
        tabs.push({
          label: this.tr("DATA"),
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

      const preResourcePromises = [];
      const store = osparc.store.Store.getInstance();
      preResourcePromises.push(store.getVisibleMembers());
      preResourcePromises.push(store.getServicesOnly(true));
      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        preResourcePromises.push(osparc.data.Resources.get("tags"));
      }
      Promise.all(preResourcePromises)
        .then(() => {
          [
            this.__studyBrowser,
            this.__templateBrowser,
            this.__serviceBrowser,
            this.__dataBrowser
          ].forEach(resourceBrowser => {
            if (resourceBrowser) {
              resourceBrowser.initResources();
            }
          });
        })
        .catch(err => console.error(err));
    },

    __createStudyBrowser: function() {
      const studiesView = this.__studyBrowser = new osparc.dashboard.StudyBrowser();
      return studiesView;
    },

    __createTemplateBrowser: function() {
      const templatesView = this.__templateBrowser = new osparc.dashboard.TemplateBrowser();
      return templatesView;
    },

    __createServiceBrowser: function() {
      const servicesView = this.__serviceBrowser = new osparc.dashboard.ServiceBrowser();
      return servicesView;
    },

    __createDataBrowser: function() {
      const dataManagerView = this.__dataBrowser = new osparc.dashboard.DataBrowser();
      return dataManagerView;
    }
  }
});
