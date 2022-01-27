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

      const qualityPage = this.__getQualityPage();
      if (qualityPage) {
        this.add(qualityPage);
      }

      const classifiersPage = this.__getClassifiersPage();
      if (classifiersPage) {
        this.add(classifiersPage);
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
        alignX: "right"
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
          this.fireEvent("updateStudy", updatedData);
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          this.fireEvent("updateTemplate", updatedData);
        }
      });
      studyDetails.addListener("updateTags", () => {
        if (osparc.utils.Resources.isTemplate(resourceData)) {
          this._resetTemplatesList(osparc.store.Store.getInstance().getTemplates());
        } else {
          this._resetStudiesList(osparc.store.Store.getInstance().getStudies());
        }
      });
      const page = this.__createPage(title, studyDetails, icon);
      return page;
    },

    __getPermissionsPage: function() {
      const title = this.tr("Permissions");
      const icon = "@FontAwesome5Solid/info";
      const resourceData = this.__resourceData;
      const studyDetails = new osparc.studycard.Large(resourceData);
      const page = this.__createPage(title, studyDetails, icon);
      return page;
    },

    __getQualityPage: function() {
      const title = this.tr("Quality");
      const icon = "@FontAwesome5Solid/info";
      const resourceData = this.__resourceData;
      const studyDetails = new osparc.studycard.Large(resourceData);
      const page = this.__createPage(title, studyDetails, icon);
      return page;
    },

    __getClassifiersPage: function() {
      const title = this.tr("Classifiers");
      const icon = "@FontAwesome5Solid/info";
      const resourceData = this.__resourceData;
      const studyDetails = new osparc.studycard.Large(resourceData);
      const page = this.__createPage(title, studyDetails, icon);
      return page;
    },

    __getServicesInStudyPage: function() {
      const title = this.tr("Services");
      const icon = "@FontAwesome5Solid/info";
      const resourceData = this.__resourceData;
      const studyDetails = new osparc.studycard.Large(resourceData);
      const page = this.__createPage(title, studyDetails, icon);
      return page;
    },

    __getSaveAsTemplatePage: function() {
      const isCurrentUserOwner = osparc.data.model.Study.isOwner(this.__resourceData);
      const canCreateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.create");
      if (isCurrentUserOwner && canCreateTemplate) {
        const title = this.tr("Save as Template");
        const icon = "@FontAwesome5Solid/info";
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
