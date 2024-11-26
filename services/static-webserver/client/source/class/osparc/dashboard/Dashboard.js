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
 * - TemplateBrowser
 * - ServiceBrowser
 * - DataBrowser
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

    osparc.utils.Utils.setIdToWidget(this.getChildControl("bar"), "dashboardTabs");
    osparc.utils.Utils.setIdToWidget(this, "dashboard");

    this.set({
      contentPadding: this.self().PADDING,
      contentPaddingBottom: 0,
      barPosition: "top"
    });

    osparc.wrapper.Plotly.getInstance().init();
    osparc.wrapper.Svg.getInstance().init();
    osparc.wrapper.JsonDiffPatch.getInstance().init();
    osparc.wrapper.JsonTreeViewer.getInstance().init();
    osparc.wrapper.DOMPurify.getInstance().init();
    osparc.wrapper.RadialMenu.getInstance().init()
      .then(loaded => {
        if (loaded) {
          // hack to trigger fonts loading
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

  statics: {
    PADDING: 15
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
      const permissions = osparc.data.Permissions.getInstance();
      const tabIconSize = 20;
      const tabs = [{
        id: "studiesTab",
        buttonId: "studiesTabBtn",
        label: osparc.product.Utils.getStudyAlias({
          plural: true,
          allUpperCase: true
        }),
        icon: "@FontAwesome5Solid/file/"+tabIconSize,
        buildLayout: this.__createStudyBrowser
      }];
      if (permissions.canDo("dashboard.templates.read")) {
        tabs.push({
          id: "templatesTab",
          buttonId: "templatesTabBtn",
          label: osparc.product.Utils.getTemplateAlias({
            plural: true,
            allUpperCase: true
          }),
          icon: "@FontAwesome5Solid/copy/"+tabIconSize,
          buildLayout: this.__createTemplateBrowser
        });
      }
      if (permissions.canDo("dashboard.services.read")) {
        tabs.push({
          id: "servicesTab",
          buttonId: "servicesTabBtn",
          label: this.tr("SERVICES"),
          icon: "@FontAwesome5Solid/cogs/"+tabIconSize,
          buildLayout: this.__createServiceBrowser
        });
      }
      if (permissions.canDo("dashboard.data.read") && osparc.product.Utils.isProduct("osparc")) {
        tabs.push({
          id: "dataTab",
          buttonId: "dataTabBtn",
          label: this.tr("DATA"),
          icon: "@FontAwesome5Solid/folder/"+tabIconSize,
          buildLayout: this.__createDataBrowser
        });
      }
      tabs.forEach(({id, buttonId, label, icon, buildLayout}) => {
        const tabPage = new qx.ui.tabview.Page(label, icon).set({
          appearance: "dashboard-page"
        });
        tabPage.id = id;
        const tabButton = tabPage.getChildControl("button");
        tabButton.set({
          minWidth: 50,
          maxHeight: 36,
        });
        tabButton.ttt = label;
        tabButton.getChildControl("label").set({
          font: "text-16"
        });
        tabButton.getChildControl("icon").set({
          visibility: "excluded"
        });
        osparc.utils.Utils.centerTabIcon(tabPage);
        osparc.utils.Utils.setIdToWidget(tabButton, buttonId);
        tabPage.setLayout(new qx.ui.layout.Grow());

        const viewLayout = buildLayout.call(this);
        tabButton.addListener("execute", () => {
          if (viewLayout.resetSelection) {
            viewLayout.resetSelection();
          }
        }, this);
        viewLayout.addListener("changeTab", e => {
          const activeTab = e.getData();
          const tabFound = this.getSelectables().find(s => s.id === activeTab);
          if (tabFound) {
            this.setSelection([tabFound]);
          }
        }, this);
        const scrollerMainView = new qx.ui.container.Scroll();
        scrollerMainView.add(viewLayout);
        tabPage.add(scrollerMainView);

        this.add(tabPage);
      }, this);

      const preResourcePromises = [];
      const groupsStore = osparc.store.Groups.getInstance();
      preResourcePromises.push(groupsStore.fetchGroupsAndMembers());
      preResourcePromises.push(osparc.store.Services.getServicesLatest(false));
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
