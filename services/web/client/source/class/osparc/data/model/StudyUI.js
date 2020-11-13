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
      workbench: studyDataUI && studyDataUI.workbench ? studyDataUI.workbench : {},
      slideshow: studyDataUI && studyDataUI.slideshow ? studyDataUI.slideshow : {},
      availableViews: studyDataUI && studyDataUI.availableViews ? studyDataUI.availableViews : this.getAvailableViews(),
      currentNodeId: studyDataUI && studyDataUI.currentNodeId ? studyDataUI.currentNodeId : null
    });
  },

  properties: {
    workbench: {
      check: "Object",
      nullable: true
    },

    slideshow: {
      check: "Object",
      nullable: true,
      event: "changeSlideshow"
    },

    availableViews: {
      check: "Array",
      init: ["workbench", "slideshow"],
      nullable: true,
      event: "changeAvailableViews"
    },

    currentNodeId: {
      check: "String",
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
      jsonObject["availableViews"] = this.getAvailableViews();
      jsonObject["currentNodeId"] = this.getCurrentNodeId();
      return jsonObject;
    }
  }
});
