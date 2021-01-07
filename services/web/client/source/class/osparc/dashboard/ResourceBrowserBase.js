/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget (base class) that shows some resources in the Dashboard.
 *
 * It used by the three tabbed elements in the main view:
 * - Study Browser
 * - Explore Browser
 * - Data Browser
 */

qx.Class.define("osparc.dashboard.ResourceBrowserBase", {
  type: "abstract",
  extend: osparc.ui.basic.LoadingPageHandler,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this._initResources();
  },

  events: {
    "startStudy": "qx.event.type.Data"
  },

  members: {
    _initResources: function() {
      throw new Error("Abstract method called!");
    },

    _getMoreInfoMenuButton: function(resourceData) {
      const moreInfoButton = new qx.ui.menu.Button(this.tr("More Info"));
      moreInfoButton.addListener("execute", () => {
        if (osparc.utils.Resources.isService(resourceData)) {
          this._openServiceDetailsEditor(resourceData);
        } else {
          const winWidth = 400;
          this.__openStudyDetailsEditor(resourceData, winWidth);
        }
      }, this);
      return moreInfoButton;
    },

    _getQualityMenuButton: function(resourceData) {
      const studyQualityButton = new qx.ui.menu.Button(this.tr("Quality"));
      studyQualityButton.addListener("execute", () => {
        this.__openQualityEditor(resourceData);
      }, this);
      return studyQualityButton;
    },

    __openStudyDetailsEditor: function(resourceData, winWidth) {
      const studyDetails = new osparc.component.metadata.StudyDetailsEditor(resourceData, osparc.utils.Resources.isTemplate(resourceData), winWidth);
      const title = this.tr("Study Details Editor");
      const win = osparc.ui.window.Window.popUpInWindow(studyDetails, title, winWidth, 400);
      studyDetails.addListener("openStudy", () => {
        this._startStudy(resourceData["uuid"]);
        win.close();
      }, this);
      studyDetails.addListener("openTemplate", () => {
        this._createStudyFromTemplate(resourceData);
        win.close();
      }, this);
      studyDetails.addListener("updateStudy", e => {
        const updatedStudyData = e.getData();
        this._reloadStudy(updatedStudyData.uuid);
        win.close();
      });
      studyDetails.addListener("updateTemplate", e => {
        const updatedTemplateData = e.getData();
        this._reloadTemplate(updatedTemplateData.uuid);
        win.close();
      }, this);
      studyDetails.addListener("updateTags", () => {
        if (osparc.utils.Resources.isTemplate(resourceData)) {
          this._resetTemplatesList(osparc.store.Store.getInstance().getTemplates());
        } else {
          this._resetStudiesList(osparc.store.Store.getInstance().getStudies());
        }
      });
    },

    _openServiceDetailsEditor: function(serviceData) {
      throw new Error("Abstract method called!");
    },

    __openQualityEditor: function(resourceData) {
      const qualityEditor = new osparc.component.metadata.QualityEditor(resourceData);
      const title = resourceData.name + " - " + this.tr("Quality Assesment");
      osparc.ui.window.Window.popUpInWindow(qualityEditor, title, 650, 760);
      qualityEditor.addListener("updateStudy", e => {
        const updatedStudyData = e.getData();
        this._resetStudyItem(updatedStudyData);
      });
      qualityEditor.addListener("updateTemplate", e => {
        const updatedTemplateData = e.getData();
        this._resetTemplateItem(updatedTemplateData);
      });
      qualityEditor.addListener("updateService", e => {
        const updatedServiceData = e.getData();
        this._resetServiceItem(updatedServiceData);
      });
    },

    _startStudy: function(studyId) {
      throw new Error("Abstract method called!");
    },

    _createStudyFromTemplate: function(templateData) {
      throw new Error("Abstract method called!");
    },

    _reloadStudy: function(studyId) {
      throw new Error("Abstract method called!");
    },

    _reloadTemplate: function(templateId) {
      throw new Error("Abstract method called!");
    },

    _resetStudyItem: function(studyData) {
      throw new Error("Abstract method called!");
    },

    _resetTemplateItem: function(templateData) {
      throw new Error("Abstract method called!");
    },

    _resetServiceItem: function(serviceData) {
      throw new Error("Abstract method called!");
    },

    _resetStudiesList: function() {
      throw new Error("Abstract method called!");
    },

    _resetTemplatesList: function() {
      throw new Error("Abstract method called!");
    }
  }
});
