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

    this.__addPages();
  },

  events: {
    "updateStudy": "qx.event.type.Data",
    "updateTemplate": "qx.event.type.Data",
    "updateService": "qx.event.type.Data",
    "updateTemplates": "qx.event.type.Event"
  },

  members: {
    __resourceData: null,
    __permissionsPage: null,
    __classifiersPage: null,
    __qualityPage: null,

    __addPages: function() {
      [
        this.__getInfoPage,
        this.__getPermissionsPage,
        this.__getClassifiersPage,
        this.__getQualityPage,
        this.__getServicesUpdatePage,
        this.__getServicesBootOptionsPage,
        this.__getSaveAsTemplatePage
      ].forEach(pageCallee => {
        const page = pageCallee.call(this);
        if (page) {
          this.add(page);
        }
      });
    },

    __createPage: function(title, widget, icon) {
      const tabPage = new qx.ui.tabview.Page().set({
        backgroundColor: "material-button-background",
        paddingLeft: 20,
        layout: new qx.ui.layout.VBox(10),
        icon: icon + "/24"
      });

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

      return tabPage;
    },

    __getInfoPage: function() {
      const title = this.tr("Information");
      const icon = "@FontAwesome5Solid/info";
      const resourceData = this.__resourceData;
      const infoCard = osparc.utils.Resources.isService(resourceData) ? new osparc.servicecard.Large(resourceData) : new osparc.studycard.Large(resourceData, false);
      infoCard.addListener("openAccessRights", () => this.setSelection([this.__permissionsPage]));
      infoCard.addListener("openClassifiers", () => this.setSelection([this.__classifiersPage]));
      infoCard.addListener("openQuality", () => this.setSelection([this.__qualityPage]));
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
      const page = this.__createPage(title, infoCard, icon);
      return page;
    },

    __getPermissionsPage: function() {
      const resourceData = this.__resourceData;
      if (osparc.utils.Resources.isTemplate(resourceData) && !osparc.data.model.Study.isOwner(resourceData)) {
        return null;
      }
      if (osparc.utils.Resources.isService(resourceData) && !osparc.data.model.Study.isOwner(resourceData)) {
        return null;
      }

      const title = this.tr("Sharing");
      const icon = "@FontAwesome5Solid/share-alt";
      const permissionsView = new osparc.component.permissions.Study(resourceData);
      permissionsView.getChildControl("study-link").show();
      permissionsView.addListener("updateAccessRights", e => {
        const updatedData = e.getData();
        if (osparc.utils.Resources.isStudy(resourceData)) {
          this.fireDataEvent("updateStudy", updatedData);
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          this.fireDataEvent("updateTemplate", updatedData);
        }
      }, this);
      const page = this.__permissionsPage = this.__createPage(title, permissionsView, icon);
      return page;
    },

    __getClassifiersPage: function() {
      if (!osparc.data.Permissions.getInstance().canDo("study.classifier")) {
        return null;
      }
      const title = this.tr("Classifiers");
      const icon = "@FontAwesome5Solid/search";
      const resourceData = this.__resourceData;
      let classifiers = null;
      if (osparc.data.model.Study.isOwner(resourceData)) {
        classifiers = new osparc.component.metadata.ClassifiersEditor(resourceData);
        classifiers.addListener("updateClassifiers", e => {
          const updatedData = e.getData();
          if (osparc.utils.Resources.isStudy(resourceData)) {
            this.fireDataEvent("updateStudy", updatedData);
          } else if (osparc.utils.Resources.isTemplate(resourceData)) {
            this.fireDataEvent("updateTemplate", updatedData);
          }
        }, this);
      } else {
        classifiers = new osparc.component.metadata.ClassifiersViewer(resourceData);
      }
      const page = this.__classifiersPage = this.__createPage(title, classifiers, icon);
      return page;
    },

    __getQualityPage: function() {
      const resourceData = this.__resourceData;
      if ("quality" in resourceData) {
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
        const page = this.__qualityPage = this.__createPage(title, qualityEditor, icon);
        return page;
      }
      return null;
    },

    __getServicesUpdatePage: function() {
      const title = this.tr("Update Services");
      const icon = "@MaterialIcons/update";
      const servicesUpdate = new osparc.component.metadata.ServicesInStudyUpdate(this.__resourceData);
      const page = this.__createPage(title, servicesUpdate, icon);
      return page;
    },

    __getServicesBootOptionsPage: function() {
      const title = this.tr("Boot Options");
      const icon = "@FontAwesome5Solid/play-circle";
      const servicesBootOpts = new osparc.component.metadata.ServicesInStudyBootOpts(this.__resourceData);
      const page = this.__createPage(title, servicesBootOpts, icon);
      return page;
    },

    __getSaveAsTemplatePage: function() {
      if (!osparc.utils.Resources.isStudy(this.__resourceData)) {
        return null;
      }

      const isCurrentUserOwner = osparc.data.model.Study.isOwner(this.__resourceData);
      const canCreateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.create");
      if (isCurrentUserOwner && canCreateTemplate) {
        const title = this.tr("Save as Template");
        const icon = "@FontAwesome5Solid/copy";
        const saveAsTemplateView = new osparc.component.study.SaveAsTemplate(this.__resourceData);
        saveAsTemplateView.addListener("finished", e => {
          const template = e.getData();
          if (template) {
            this.fireEvent("updateTemplates");
          }
        }, this);
        const page = this.__createPage(title, saveAsTemplateView, icon);
        return page;
      }
      return null;
    }
  }
});
