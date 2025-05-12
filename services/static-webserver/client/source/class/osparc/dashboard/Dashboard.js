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
 * - AppBrowser
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

    // osparc.wrapper.Plotly.getInstance().init();
    // osparc.wrapper.Three.getInstance().init();
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
    __hypertoolBrowser: null,
    __appBrowser: null,
    __dataBrowser: null,

    getStudyBrowser: function() {
      return this.__studyBrowser;
    },

    getTemplateBrowser: function() {
      return this.__templateBrowser;
    },

    getAppBrowser: function() {
      return this.__appBrowser;
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
        if (osparc.product.Utils.isS4LProduct() && osparc.store.StaticInfo.getInstance().isDevFeaturesEnabled()) {
          tabs.push({
            id: "hypertoolsTab",
            buttonId: "hypertoolsTabBtn",
            label: this.tr("HYPERTOOLS"),
            icon: "@FontAwesome5Solid/copy/"+tabIconSize,
            // initVisibility: "excluded",
            buildLayout: this.__createHypertoolsBrowser
          });
        }
      }
      if (permissions.canDo("dashboard.services.read")) {
        tabs.push({
          id: "appsTab",
          buttonId: "appsTabBtn",
          label: this.tr("APPS"),
          icon: "@FontAwesome5Solid/cogs/"+tabIconSize,
          buildLayout: this.__createAppBrowser
        });
      }
      if (permissions.canDo("dashboard.data.read")) {
        tabs.push({
          id: "dataTab",
          buttonId: "dataTabBtn",
          label: this.tr("DATA"),
          icon: "@FontAwesome5Solid/folder/"+tabIconSize,
          buildLayout: this.__createDataBrowser
        });
      }
      tabs.forEach(({id, buttonId, label, icon, initVisibility, buildLayout}) => {
        const tabPage = new qx.ui.tabview.Page(label, icon).set({
          appearance: "dashboard-page"
        });
        tabPage.id = id;
        const tabButton = tabPage.getChildControl("button");
        tabButton.set({
          minWidth: 50,
          maxHeight: 36,
          visibility: initVisibility ? initVisibility : "visible",
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

        const resourceBrowser = buildLayout.call(this);
        tabButton.addListener("execute", () => {
          if (resourceBrowser.resetSelection) {
            resourceBrowser.resetSelection();
          }
        }, this);

        resourceBrowser.addListener("changeTab", e => {
          const activeTab = e.getData();
          const tabFound = this.getSelectables().find(s => s.id === activeTab);
          if (tabFound) {
            this.setSelection([tabFound]);
          }
        }, this);

        const scrollerMainView = new qx.ui.container.Scroll();
        scrollerMainView.add(resourceBrowser);
        tabPage.add(scrollerMainView);
        tabPage.resourceBrowser = resourceBrowser;

        this.add(tabPage);
      }, this);

      const preResourcePromises = [];
      const groupsStore = osparc.store.Groups.getInstance();
      preResourcePromises.push(groupsStore.fetchGroupsAndMembers());
      preResourcePromises.push(osparc.store.Services.getServicesLatest(false));
      Promise.all(preResourcePromises)
        .then(() => {
          if (this.__studyBrowser) {
            this.__studyBrowser.initResources();
          }
          if (this.__appBrowser) {
            this.__appBrowser.initResources();
          }
          if (this.__dataBrowser) {
            this.__dataBrowser.initResources();
          }

          this.addListener("changeSelection", e => {
            const selectedTab = e.getData()[0];
            if (selectedTab && selectedTab.resourceBrowser) {
              selectedTab.resourceBrowser.initResources();
            }
          }, this);
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

    __createHypertoolsBrowser: function() {
      const templateType = osparc.data.model.StudyUI.HYPERTOOL_TYPE;
      const hypertoolsView = this.__hypertoolBrowser = new osparc.dashboard.TemplateBrowser(templateType);
      return hypertoolsView;
    },

    __createAppBrowser: function() {
      const appsView = this.__appBrowser = new osparc.dashboard.AppBrowser();
      return appsView;
    },

    __createDataBrowser: function() {
      const dataManagerView = this.__dataBrowser = new osparc.dashboard.DataBrowser();
      return dataManagerView;
    }
  }
});
