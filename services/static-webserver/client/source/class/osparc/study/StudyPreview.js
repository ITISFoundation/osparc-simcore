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
   * @param studyData {osparc.data.model.Study|Object} Study or Serialized Study Object
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
      if (osparc.product.Utils.showStudyPreview(this.__studyData) && !this.__studyData.isPipelineEmpty()) {
        this.add(new osparc.dashboard.StudyThumbnailExplorer(this.__studyData));
      }
    }
  }
});
