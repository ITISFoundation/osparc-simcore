/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.ResourceMoreOptions", {
  extend: qx.ui.tabview.TabView,

  construct: function(resourceData) {
    this.base(arguments);

    this.__resourceData = resourceData;

    this.set({
      barPosition: "left",
      contentPadding: 0
    });

    if (osparc.utils.Resources.isService(resourceData)) {
      this.__createServiceVersionSelector();
    }

    this.__addPages();
  },

  events: {
    "updateStudy": "qx.event.type.Data",
    "updateTemplate": "qx.event.type.Data",
    "updateService": "qx.event.type.Data",
    "publishTemplate": "qx.event.type.Data",
    "openService": "qx.event.type.Data"
  },

  members: {
    __resourceData: null,
    __serviceVersionLayout: null,
    __serviceVersionSelector: null,
    __permissionsPage: null,
    __classifiersPage: null,
    __qualityPage: null,
    __servicesUpdatePage: null,

    __openPage: function(page) {
      if (page) {
        this.setSelection([page]);
      }
    },

    openAccessRights: function() {
      this.__openPage(this.__permissionsPage);
    },

    openClassifiers: function() {
      this.__openPage(this.__classifiersPage);
    },

    openQuality: function() {
      this.__openPage(this.__qualityPage);
    },

    openUpdateServices: function() {
      this.__openPage(this.__servicesUpdatePage);
    },

    __createServiceVersionSelector: function() {
      const hBox = this.__serviceVersionLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));

      const versionLabel = new qx.ui.basic.Label(this.tr("Service Version"));
      hBox.add(versionLabel);
      const versionsBox = this.__serviceVersionSelector = new osparc.ui.toolbar.SelectBox();
      hBox.add(versionsBox);

      // populate it with owned versions
      const store = osparc.store.Store.getInstance();
      store.getAllServices()
        .then(services => {
          const versions = osparc.utils.Services.getVersions(services, this.__resourceData["key"]);
          const selectBox = this.__serviceVersionSelector;
          let selectedItem = null;
          versions.reverse().forEach(version => {
            selectedItem = new qx.ui.form.ListItem(version);
            selectBox.add(selectedItem);
            if (this.__resourceData["version"] === version) {
              selectBox.setSelection([selectedItem]);
            }
          });
        });

      versionsBox.addListener("changeSelection", () => {
        const selection = versionsBox.getSelection();
        if (selection && selection.length) {
          const serviceVersion = selection[0].getLabel();
          if (serviceVersion !== this.__resourceData["version"]) {
            store.getAllServices()
              .then(services => {
                const serviceData = osparc.utils.Services.getFromObject(services, this.__resourceData["key"], serviceVersion);
                console.log(serviceData);
                serviceData["resourceType"] = "service";
                this.__resourceData = serviceData;
                this.__addPages();
              });
          }
        }
      }, this);

      return hBox;
    },

    __addPages: function() {
      // keep selected page
      const selection = this.getSelection();
      const selectedTabId = selection.length ? selection[0]["tabId"] : null;

      // removeAll
      const pages = this.getChildren().length;
      for (let i=pages-1; i>=0; i--) {
        this.remove(this.getChildren()[i]);
      }

      // add Open service button
      [
        this.__getInfoPage,
        this.__getPermissionsPage,
        this.__getClassifiersPage,
        this.__getQualityPage,
        this.__getServicesUpdatePage,
        this.__getServicesBootOptionsPage,
        this.__getSaveAsTemplatePage
      ].forEach(pageCallee => {
        if (pageCallee) {
          const page = pageCallee.call(this);
          if (page) {
            this.add(page);
          }
        }
      });

      if (selectedTabId) {
        const pageFound = this.getChildren().find(page => page.tabId === selectedTabId);
        if (pageFound) {
          this.setSelection([pageFound]);
        }
      }
    },

    __createPage: function(title, widget, icon, id) {
      const tabPage = new qx.ui.tabview.Page().set({
        backgroundColor: "background-main-2",
        paddingLeft: 20,
        layout: new qx.ui.layout.VBox(10),
        icon: icon + "/24"
      });
      tabPage.tabId = id;

      tabPage.getButton().set({
        minWidth: 35,
        toolTipText: title,
        alignY: "middle"
      });
      tabPage.getButton().getChildControl("icon").set({
        alignX: "center"
      });

      // Page title
      tabPage.add(new qx.ui.basic.Label(title).set({
        font: "title-16"
      }));

      // Page content
      tabPage.add(widget, {
        flex: 1
      });

      if (osparc.utils.Resources.isService(this.__resourceData)) {
        this.addListener("changeSelection", e => {
          const currentSelection = e.getData()[0];
          if (currentSelection === tabPage) {
            tabPage.addAt(this.__serviceVersionLayout, 1);
          }
        }, this);
      }

      return tabPage;
    },

    __getInfoPage: function() {
      const id = "Information";
      const title = this.tr("Information");
      const icon = "@FontAwesome5Solid/info";
      const resourceData = this.__resourceData;
      const infoCard = osparc.utils.Resources.isService(resourceData) ? new osparc.info.ServiceLarge(resourceData, null, false) : new osparc.info.StudyLarge(resourceData, false);
      infoCard.addListener("openAccessRights", () => this.openAccessRights());
      infoCard.addListener("openClassifiers", () => this.openClassifiers());
      infoCard.addListener("openQuality", () => this.openQuality());
      infoCard.addListener("updateStudy", e => {
        const updatedData = e.getData();
        if (osparc.utils.Resources.isStudy(resourceData)) {
          this.fireDataEvent("updateStudy", updatedData);
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          this.fireDataEvent("updateTemplate", updatedData);
        }
      });
      infoCard.addListener("updateService", e => {
        const updatedData = e.getData();
        if (osparc.utils.Resources.isService(resourceData)) {
          this.fireDataEvent("updateService", updatedData);
        }
      });
      infoCard.addListener("updateTags", e => {
        const updatedData = e.getData();
        if (osparc.utils.Resources.isStudy(resourceData)) {
          this.fireDataEvent("updateStudy", updatedData);
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          this.fireDataEvent("updateTemplate", updatedData);
        }
      });
      const page = this.__createPage(title, infoCard, icon, id);

      if (osparc.utils.Resources.isService(resourceData)) {
        const openServiceButton = new qx.ui.form.Button(this.tr("Open")).set({
          appearance: "strong-button",
          allowGrowX: false,
          alignX: "right"
        });
        openServiceButton.addListener("execute", () => {
          this.fireDataEvent("openService", {
            key: resourceData["key"],
            version: resourceData["version"]
          });
        });
        page.add(openServiceButton);
      }

      return page;
    },

    __getPermissionsPage: function() {
      const id = "Permissions";
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isTemplate(resourceData) && !osparc.data.model.Study.canIWrite(resourceData["accessRights"])) {
        return null;
      }
      if (osparc.utils.Resources.isService(resourceData) && !osparc.utils.Services.canIWrite(resourceData["accessRights"])) {
        return null;
      }

      const title = this.tr("Sharing");
      const icon = "@FontAwesome5Solid/share-alt";
      let permissionsView = null;
      if (osparc.utils.Resources.isService(resourceData)) {
        permissionsView = new osparc.component.permissions.Service(resourceData);
        permissionsView.addListener("updateAccessRights", e => {
          const updatedData = e.getData();
          if (osparc.utils.Resources.isService(resourceData)) {
            this.fireDataEvent("updateService", updatedData);
          }
        }, this);
      } else {
        permissionsView = new osparc.component.permissions.Study(resourceData);
        if (osparc.utils.Resources.isStudy(resourceData)) {
          permissionsView.getChildControl("study-link").show();
        }
        permissionsView.addListener("updateAccessRights", e => {
          const updatedData = e.getData();
          if (osparc.utils.Resources.isStudy(resourceData)) {
            this.fireDataEvent("updateStudy", updatedData);
          } else if (osparc.utils.Resources.isTemplate(resourceData)) {
            this.fireDataEvent("updateTemplate", updatedData);
          }
        }, this);
      }
      const page = this.__permissionsPage = this.__createPage(title, permissionsView, icon, id);

      return page;
    },

    __getClassifiersPage: function() {
      const id = "Classfiiers";
      if (!osparc.data.Permissions.getInstance().canDo("study.classifier")) {
        return null;
      }
      const title = this.tr("Classifiers");
      const icon = "@FontAwesome5Solid/search";
      const resourceData = this.__resourceData;
      let classifiers = null;
      if (
        (osparc.utils.Resources.isStudy(resourceData) || osparc.utils.Resources.isTemplate(resourceData)) && osparc.data.model.Study.canIWrite(resourceData["accessRights"]) ||
        osparc.utils.Resources.isService(resourceData) && osparc.utils.Services.canIWrite(resourceData["accessRights"])
      ) {
        classifiers = new osparc.component.metadata.ClassifiersEditor(resourceData);
        classifiers.addListener("updateClassifiers", e => {
          const updatedData = e.getData();
          if (osparc.utils.Resources.isStudy(resourceData)) {
            this.fireDataEvent("updateStudy", updatedData);
          } else if (osparc.utils.Resources.isTemplate(resourceData)) {
            this.fireDataEvent("updateTemplate", updatedData);
          } else if (osparc.utils.Resources.isService(resourceData)) {
            this.fireDataEvent("updateService", updatedData);
          }
        }, this);
      } else {
        classifiers = new osparc.component.metadata.ClassifiersViewer(resourceData);
      }
      const page = this.__classifiersPage = this.__createPage(title, classifiers, icon, id);
      return page;
    },

    __getQualityPage: function() {
      if (osparc.utils.Utils.isProduct("s4llite")) {
        return null;
      }
      const id = "Quality";
      const resourceData = this.__resourceData;
      if (
        "quality" in resourceData &&
        (!osparc.utils.Resources.isService(resourceData) || osparc.data.model.Node.isComputational(resourceData))
      ) {
        const title = this.tr("Quality");
        const icon = "@FontAwesome5Solid/star-half";
        const qualityEditor = new osparc.component.metadata.QualityEditor(resourceData);
        qualityEditor.addListener("updateQuality", e => {
          const updatedData = e.getData();
          if (osparc.utils.Resources.isStudy(resourceData)) {
            this.fireDataEvent("updateStudy", updatedData);
          } else if (osparc.utils.Resources.isTemplate(resourceData)) {
            this.fireDataEvent("updateTemplate", updatedData);
          }
        });
        const page = this.__qualityPage = this.__createPage(title, qualityEditor, icon, id);
        return page;
      }
      return null;
    },

    __getServicesUpdatePage: function() {
      const id = "ServicesUpdate";
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isService(resourceData)) {
        return null;
      }

      const title = this.tr("Update Services");
      const icon = "@MaterialIcons/update";
      const servicesUpdate = new osparc.component.metadata.ServicesInStudyUpdate(resourceData);
      servicesUpdate.addListener("updateService", e => {
        const updatedData = e.getData();
        if (osparc.utils.Resources.isStudy(resourceData)) {
          this.fireDataEvent("updateStudy", updatedData);
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          this.fireDataEvent("updateTemplate", updatedData);
        }
      });
      const page = this.__servicesUpdatePage = this.__createPage(title, servicesUpdate, icon, id);
      return page;
    },

    __getServicesBootOptionsPage: function() {
      const id = "ServicesBootOptions";
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isService(resourceData)) {
        return null;
      }
      if (!osparc.component.metadata.ServicesInStudyBootOpts.anyBootOptions(resourceData)) {
        return null;
      }

      const title = this.tr("Boot Options");
      const icon = "@FontAwesome5Solid/play-circle";
      const servicesBootOpts = new osparc.component.metadata.ServicesInStudyBootOpts(resourceData);
      const page = this.__createPage(title, servicesBootOpts, icon, id);
      return page;
    },

    __getSaveAsTemplatePage: function() {
      const id = "SaveAsTemplate";
      if (!osparc.utils.Resources.isStudy(this.__resourceData)) {
        return null;
      }

      const canIWrite = osparc.data.model.Study.canIWrite(this.__resourceData["accessRights"]);
      const canCreateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.create");
      if (canIWrite && canCreateTemplate) {
        const title = this.tr("Save as Template");
        const icon = "@FontAwesome5Solid/copy";
        const saveAsTemplate = new osparc.component.study.SaveAsTemplate(this.__resourceData);
        saveAsTemplate.addListener("publishTemplate", e => this.fireDataEvent("publishTemplate", e.getData()));
        const page = this.__createPage(title, saveAsTemplate, icon, id);
        return page;
      }
      return null;
    }
  }
});
