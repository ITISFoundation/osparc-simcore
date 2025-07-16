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

    if (study instanceof osparc.data.model.Study) {
      const uiMode = study.getUi().getMode();
      if (["workbench", "pipeline"].includes(uiMode)) {
        this.__buildPreview(study);
      }
    } else if (study instanceof osparc.data.model.Function) {
      this.__buildPreview(study);
    }
  },

  members: {
    __buildPreview: function(study) {
      const workbenchReady = () => {
        const workbenchUIPreview = new osparc.workbench.WorkbenchUIPreview();
        if (study instanceof osparc.data.model.Study) {
          workbenchUIPreview.setStudy(study);
        } else if (study instanceof osparc.data.model.Function) {
          workbenchUIPreview.setFunction(study);
        }
        workbenchUIPreview.loadModel(study.getWorkbench());
        workbenchUIPreview.setMaxHeight(550);
        this._add(workbenchUIPreview);
      };

      if (study.getWorkbench().isDeserialized()) {
        workbenchReady();
      } else {
        study.getWorkbench().addListenerOnce("changeDeserialized", e => {
          if (e.getData()) {
            workbenchReady();
          }
        }, this);
      }
    }
  }
});
