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
   * @param studyData {Object} Serialized Study Object
   */
  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__studyData = studyData;

    this.__buildLayout();
  },

  members: {
    __studyData: null,

    __buildLayout: function() {
      this.__buildPreview();
    },

    __buildPreview: function() {
      const study = new osparc.data.model.Study(this.__studyData);
      const uiMode = osparc.data.model.Study.getUiMode(this.__studyData);
      if (uiMode !== "app" && !study.isPipelineEmpty()) {
        const workbenchUIPreview = new osparc.workbench.WorkbenchUIPreview();
        workbenchUIPreview.setStudy(study);
        workbenchUIPreview.loadModel(study.getWorkbench());
        workbenchUIPreview.setMaxHeight(550);
        this._add(workbenchUIPreview);
      }
    }
  }
});
