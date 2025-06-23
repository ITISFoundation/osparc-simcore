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

  members: {
    __study: null,

    __buildPreview: function() {
      const study = this.__study;

      const workbenchReady = () => {
        if (!study.isPipelineEmpty()) {
          const workbenchUIPreview = new osparc.workbench.WorkbenchUIPreview();
          workbenchUIPreview.setStudy(study);
          workbenchUIPreview.loadModel(study.getWorkbench());
          workbenchUIPreview.setMaxHeight(550);
          this._add(workbenchUIPreview);
        }
      };

      const uiMode = study.getUi().getMode();
      if (["workbench", "pipeline"].includes(uiMode)) {
        if (study.getWorkbench().isDeserialized()) {
          workbenchReady();
        } else {
          study.getWorkbench().addListener("changeDeserialized", e => {
            if (e.getData()) {
              workbenchReady();
            }
          }, this);
        }
      }
    }
  }
});
