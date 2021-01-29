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
      osparc.utils.Utils.setIdToWidget(moreInfoButton, "moreInfoBtn");
      moreInfoButton.addListener("execute", () => {
        if (osparc.utils.Resources.isService(resourceData)) {
          this._openServiceDetailsEditor(resourceData);
        } else {
          this.__openStudyDetails(resourceData);
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

    __openStudyDetails: function(resourceData) {
      const studyDetails = new osparc.studycard.Large(resourceData);
      const title = this.tr("Study Details");
      const width = 500;
      const height = 500;
      osparc.ui.window.Window.popUpInWindow(studyDetails, title, width, height);
      studyDetails.addListener("updateStudy", e => {
        if (osparc.utils.Resources.isTemplate(resourceData)) {
          const updatedTemplateData = e.getData();
          this._reloadTemplate(updatedTemplateData.uuid);
        } else {
          const updatedStudyData = e.getData();
          this._reloadStudy(updatedStudyData.uuid);
        }
      });
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
      const qualityEditor = osparc.studycard.Utils.openQuality(resourceData);
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
