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
    "updateStudies": "qx.event.type.Event",
    "updateTemplates": "qx.event.type.Event"
  },

  members: {
    __resourceData: null,

    __addPages: function() {
      const moreInfoPage = this.__getInfoPage();
      if (moreInfoPage) {
        this.add(moreInfoPage);
      }

      const permissionsPage = this.__getPermissionsPage();
      if (permissionsPage) {
        this.add(permissionsPage);
      }

      const classifiersPage = this.__getClassifiersPage();
      if (classifiersPage) {
        this.add(classifiersPage);
      }

      const qualityPage = this.__getQualityPage();
      if (qualityPage) {
        this.add(qualityPage);
      }

      const servicesInStudyPage = this.__getServicesInStudyPage();
      if (servicesInStudyPage) {
        this.add(servicesInStudyPage);
      }

      const saveAsTemplatePage = this.__getSaveAsTemplatePage();
      if (saveAsTemplatePage) {
        this.add(saveAsTemplatePage);
      }
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
      const studyDetails = new osparc.studycard.Large(resourceData);
      studyDetails.addListener("updateStudy", e => {
        const updatedData = e.getData();
        if (osparc.utils.Resources.isStudy(resourceData)) {
          this.fireDataEvent("updateStudy", updatedData);
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          this.fireDataEvent("updateTemplate", updatedData);
        }
      });
      studyDetails.addListener("updateTags", () => {
        if (osparc.utils.Resources.isStudy(resourceData)) {
          this.fireEvent("updateStudies");
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          this.fireEvent("updateTemplates");
        }
      });
      const page = this.__createPage(title, studyDetails, icon);
      return page;
    },

    __getPermissionsPage: function() {
      const title = this.tr("Sharing");
      const icon = "@FontAwesome5Solid/share-alt";
      const resourceData = this.__resourceData;
      const permissionsView = new osparc.component.permissions.Study(resourceData);
      permissionsView.getChildControl("study-link").show();
      permissionsView.addListener("updateAccessRights", e => {
        const updatedData = e.getData();
        this.fireDataEvent("updateStudy", updatedData);
      }, this);
      const page = this.__createPage(title, permissionsView, icon);
      return page;
    },

    __getQualityPage: function() {
      const title = this.tr("Quality");
      const icon = "@FontAwesome5Solid/star-half";
      const resourceData = this.__resourceData;
      const qualityEditor = new osparc.component.metadata.QualityEditor(resourceData);
      qualityEditor.addListener("updateQuality", e => {
        const updatedData = e.getData();
        if (osparc.utils.Resources.isStudy(resourceData)) {
          this.fireDataEvent("updateStudy", updatedData);
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          this.fireDataEvent("updateTemplate", updatedData);
        } else if (osparc.utils.Resources.isService(resourceData)) {
          this.fireDataEvent("updateService", updatedData);
        }
      });
      const page = this.__createPage(title, qualityEditor, icon);
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
          this.fireDataEvent("updateStudy", updatedData);
        }, this);
      } else {
        classifiers = new osparc.component.metadata.ClassifiersViewer(resourceData);
      }
      const page = this.__createPage(title, classifiers, icon);
      return page;
    },

    __getServicesInStudyPage: function() {
      const title = this.tr("Services");
      const icon = "@MaterialIcons/update";
      const resourceData = this.__resourceData;
      const servicesInStudy = new osparc.component.metadata.ServicesInStudy(resourceData);
      const page = this.__createPage(title, servicesInStudy, icon);
      return page;
    },

    __getSaveAsTemplatePage: function() {
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
