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
  extend: qx.ui.core.Widget,

  construct: function(resourceData) {
    this.base(arguments);

    this.__resourceData = resourceData;

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__addToolbar();
    this.__addDetailsView();
  },

  events: {
    "updateStudy": "qx.event.type.Data",
    "updateTemplate": "qx.event.type.Data",
    "updateService": "qx.event.type.Data",
    "publishTemplate": "qx.event.type.Data",
    "openService": "qx.event.type.Data"
  },

  statics: {
    WIDTH: 700,
    HEIGHT: 700,

    popUpInWindow: function(moreOpts) {
      const title = qx.locale.Manager.tr("Details");
      return osparc.ui.window.Window.popUpInWindow(moreOpts, title, this.WIDTH, this.HEIGHT);
    },

    createPage: function(title, widget, icon, id) {
      const tabPage = new qx.ui.tabview.Page().set({
        backgroundColor: "background-main-2",
        paddingLeft: 20,
        layout: new qx.ui.layout.VBox(10),
        icon: icon + "/24"
      });
      tabPage.tabId = id;

      tabPage.getButton().set({
        minWidth: 35,
        toolTipText: title
      });
      osparc.utils.Utils.centerTabIcon(tabPage);

      // Page title
      tabPage.add(new qx.ui.basic.Label(title).set({
        font: "text-15"
      }));

      // Page content
      tabPage.add(widget, {
        flex: 1
      });

      return tabPage;
    }
  },

  properties: {
    showOpenButton: {
      check: "Boolean",
      init: true,
      nullable: false,
      event: "changeShowOpenButton"
    }
  },

  members: {
    __resourceData: null,
    __toolbar: null,
    __detailsView: null,
    __permissionsPage: null,
    __tagsPage: null,
    __classifiersPage: null,
    __qualityPage: null,
    __servicesUpdatePage: null,

    __addToolbar: function() {
      const toolbar = this.__toolbar = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isService(resourceData)) {
        const serviceVersionSelector = this.__createServiceVersionSelector();
        toolbar.add(serviceVersionSelector);
      }

      toolbar.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      if (osparc.utils.Resources.isService(resourceData)) {
        const openButton = new qx.ui.form.Button(this.tr("Open")).set({
          appearance: "strong-button",
          font: "text-14",
          alignX: "right",
          height: 24
        });
        this.bind("showOpenButton", openButton, "visibility", {
          converter: show => show ? "visible" : "excluded"
        });
        openButton.addListener("execute", () => {
          this.fireDataEvent("openService", {
            key: this.__resourceData["key"],
            version: this.__resourceData["version"]
          });
        });
        toolbar.add(openButton);
      }

      this._add(toolbar);
    },

    __addDetailsView: function() {
      const detailsView = this.__detailsView = new qx.ui.tabview.TabView().set({
        barPosition: "left",
        contentPadding: 0
      });
      this._add(detailsView, {
        flex: 1
      });

      this.__addPages();
    },

    __openPage: function(page) {
      if (page) {
        this.setSelection([page]);
      }
    },

    openAccessRights: function() {
      this.__openPage(this.__permissionsPage);
    },

    openTags: function() {
      this.__openPage(this.__tagsPage);
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
      const versionsBox = new osparc.ui.toolbar.SelectBox();
      hBox.add(versionsBox);

      // populate it with owned versions
      const store = osparc.store.Store.getInstance();
      store.getAllServices()
        .then(services => {
          const versions = osparc.utils.Services.getVersions(services, this.__resourceData["key"]);
          let selectedItem = null;
          versions.reverse().forEach(version => {
            selectedItem = new qx.ui.form.ListItem(version);
            versionsBox.add(selectedItem);
            if (this.__resourceData["version"] === version) {
              versionsBox.setSelection([selectedItem]);
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
      const detailsView = this.__detailsView;

      // keep selected page
      const selection = detailsView.getSelection();
      const selectedTabId = selection.length ? selection[0]["tabId"] : null;

      // removeAll
      const pages = detailsView.getChildren().length;
      for (let i=pages-1; i>=0; i--) {
        detailsView.remove(detailsView.getChildren()[i]);
      }

      // add Open service button
      [
        this.__getInfoPage,
        this.__getPermissionsPage,
        this.__getTagsPage,
        this.__getServicesUpdatePage,
        this.__getServicesBootOptionsPage,
        this.__getQualityPage,
        this.__getClassifiersPage,
        this.__getSaveAsTemplatePage
      ].forEach(pageCallee => {
        if (pageCallee) {
          const page = pageCallee.call(this);
          if (page) {
            detailsView.add(page);
          }
        }
      });

      if (selectedTabId) {
        const pageFound = detailsView.getChildren().find(page => page.tabId === selectedTabId);
        if (pageFound) {
          detailsView.setSelection([pageFound]);
        }
      }
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
      infoCard.addListener("openTags", () => this.openTags());
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
      const page = this.self().createPage(title, infoCard, icon, id);

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

      let resourceLabel = "";
      if (osparc.utils.Resources.isService(resourceData)) {
        resourceLabel = this.tr("service");
      } else if (osparc.utils.Resources.isTemplate(resourceData)) {
        resourceLabel = osparc.product.Utils.getTemplateAlias();
      } else if (osparc.utils.Resources.isStudy(resourceData)) {
        resourceLabel = osparc.product.Utils.getStudyAlias();
      }
      const title = this.tr("Share ") + resourceLabel;
      const icon = "@FontAwesome5Solid/share-alt";
      let permissionsView = null;
      if (osparc.utils.Resources.isService(resourceData)) {
        permissionsView = new osparc.component.share.CollaboratorsService(resourceData);
        permissionsView.addListener("updateAccessRights", e => {
          const updatedData = e.getData();
          if (osparc.utils.Resources.isService(resourceData)) {
            this.fireDataEvent("updateService", updatedData);
          }
        }, this);
      } else {
        permissionsView = new osparc.component.share.CollaboratorsStudy(resourceData);
        if (osparc.utils.Resources.isStudy(resourceData)) {
          permissionsView.getChildControl("study-link").show();
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          permissionsView.getChildControl("template-link").show();
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
      const page = this.__permissionsPage = this.self().createPage(title, permissionsView, icon, id);

      return page;
    },

    __getClassifiersPage: function() {
      if (!osparc.product.Utils.showClassifiers()) {
        return null;
      }
      const id = "Classifiers";
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
      const page = this.__classifiersPage = this.self().createPage(title, classifiers, icon, id);
      return page;
    },

    __getQualityPage: function() {
      if (!osparc.product.Utils.showQuality()) {
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
        const page = this.__qualityPage = this.self().createPage(title, qualityEditor, icon, id);
        return page;
      }
      return null;
    },

    __getTagsPage: function() {
      const id = "Tags";
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isService(resourceData)) {
        return null;
      }
      if (!osparc.data.model.Study.canIWrite(resourceData["accessRights"])) {
        return null;
      }

      const title = this.tr("Tags");
      const icon = "@FontAwesome5Solid/tags";
      const tagManager = new osparc.component.form.tag.TagManager(resourceData);
      tagManager.addListener("updateTags", e => {
        const updatedData = e.getData();
        tagManager.setStudydata(updatedData);
        this.fireDataEvent("updateStudy", updatedData);
      }, this);
      const page = this.__tagsPage = this.self().createPage(title, tagManager, icon, id);
      return page;
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
      const page = this.__servicesUpdatePage = this.self().createPage(title, servicesUpdate, icon, id);
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
      const page = this.self().createPage(title, servicesBootOpts, icon, id);
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
        const title = this.tr("Save as ") + osparc.utils.Utils.capitalize(osparc.product.Utils.getTemplateAlias());
        const icon = "@FontAwesome5Solid/copy";
        const saveAsTemplate = new osparc.component.study.SaveAsTemplate(this.__resourceData);
        saveAsTemplate.addListener("publishTemplate", e => this.fireDataEvent("publishTemplate", e.getData()));
        const page = this.self().createPage(title, saveAsTemplate, icon, id);
        return page;
      }
      return null;
    }
  }
});
