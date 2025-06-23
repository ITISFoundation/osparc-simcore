/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Julian Querido (jsaq007)

************************************************************************ */

qx.Class.define("osparc.study.StudyPreview", {
  extend: qx.ui.core.Widget,

  /**
   * @param study {osparc.data.model.Study} Study model
   */
  construct: function(study) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__study = study;

    this.__buildPreview();
  },

  statics: {
    __popUpPreview: function(studyData) {
      const cantReadServices = osparc.study.Utils.getCantReadServices(studyData["services"]);
      if (cantReadServices && cantReadServices.length) {
        osparc.FlashMessenger.logError("Function Data not available");
        return;
      }

      const study = new osparc.data.model.Study(studyData);
      // make sure it will be shown
      study.getUi().setMode("pipeline");

      const studyReady = () => {
        const preview = new osparc.study.StudyPreview(study);
        const title = qx.locale.Manager.tr("Function Preview");
        const width = osparc.dashboard.ResourceDetails.WIDTH;
        const height = osparc.dashboard.ResourceDetails.HEIGHT;
        osparc.ui.window.Window.popUpInWindow(preview, title, width, height).set({
          clickAwayClose: false,
          resizable: true,
          showClose: true,
        });
      }

      if (study.getWorkbench().isDeserialized()) {
        studyReady();
      } else {
        study.getWorkbench().addListener("changeDeserialized", e => {
          if (e.getData()) {
            studyReady();
          }
        }, this);
      }
    },

    popUpPreview: function(studyData) {
      if ("services" in studyData) {
        this.__popUpPreview(studyData);
      } else {
        osparc.store.Services.getStudyServices(studyData["uuid"])
          .then(resp => {
            const services = resp["services"];
            studyData["services"] = services;
            this.__popUpPreview(studyData);
          });
      }
    }
  },

  members: {
    __study: null,

    __buildPreview: function() {
      const study = this.__study;
      const uiMode = study.getUi().getMode();
      if (["workbench", "pipeline"].includes(uiMode) && !study.isPipelineEmpty()) {
        const workbenchUIPreview = new osparc.workbench.WorkbenchUIPreview();
        workbenchUIPreview.setStudy(study);
        workbenchUIPreview.loadModel(study.getWorkbench());
        workbenchUIPreview.setMaxHeight(550);
        this._add(workbenchUIPreview);
      }
    }
  }
});
