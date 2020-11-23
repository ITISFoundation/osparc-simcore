/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.data.model.StudyUI", {
  extend: qx.core.Object,

  /**
   * @param studyDataUI {Object} Object containing the serialized Study UI Data
   */
  construct: function(studyDataUI) {
    this.base(arguments);

    this.set({
      workbench: studyDataUI && studyDataUI.workbench ? studyDataUI.workbench : this.getWorkbench(),
      slideshow: studyDataUI && studyDataUI.slideshow ? studyDataUI.slideshow : this.getSlideshow(),
      currentNodeId: studyDataUI && studyDataUI.currentNodeId ? studyDataUI.currentNodeId : this.getCurrentNodeId()
    });
  },

  properties: {
    workbench: {
      check: "Object",
      init: {},
      nullable: true
    },

    slideshow: {
      check: "Object",
      init: {},
      nullable: true,
      event: "changeSlideshow"
    },

    currentNodeId: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeCurrentNodeId"
    }
  },

  members: {
    serialize: function() {
      const currentStudy = osparc.store.Store.getInstance().getCurrentStudy();
      let jsonObject = {};
      jsonObject["workbench"] = currentStudy ? currentStudy.getWorkbench().serializeUI() : this.getWorkbench();
      jsonObject["slideshow"] = this.getSlideshow();
      jsonObject["currentNodeId"] = this.getCurrentNodeId();
      return jsonObject;
    }
  }
});
