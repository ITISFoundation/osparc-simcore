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
      slideshow: new osparc.data.model.Slideshow(studyDataUI && studyDataUI.slideshow ? studyDataUI.slideshow : this.getSlideshow()),
      currentNodeId: studyDataUI && studyDataUI.currentNodeId ? studyDataUI.currentNodeId : this.initCurrentNodeId(),
      mode: studyDataUI && studyDataUI.mode ? studyDataUI.mode : this.initMode(),
      annotations: {},
      templateType: studyDataUI && studyDataUI.templateType ? studyDataUI.templateType : null,
    });

    if ("annotations" in studyDataUI) {
      this.__annotationsInitData = studyDataUI["annotations"];
    }
  },

  properties: {
    // stores position and/or marker
    workbench: {
      check: "Object",
      init: {},
      nullable: true
    },

    slideshow: {
      check: "osparc.data.model.Slideshow",
      init: {},
      nullable: true
    },

    currentNodeId: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeCurrentNodeId"
    },

    mode: {
      check: [
        "workbench", // =auto, the frontend decides the icon and default view
        "app", "guided", // "guided" is no longer used
        "standalone",
        "pipeline",
      ],
      init: "workbench",
      nullable: true,
      event: "changeMode",
      apply: "__applyMode"
    },

    annotations: {
      check: "Object",
      init: {},
      nullable: true
    },

    templateType: {
      check: [null, "hypertool", "tutorial", "template"],
      init: null,
      nullable: true,
      event: "changeTemplateType",
    },
  },

  statics: {
    TEMPLATE_TYPE: "TEMPLATE",
    TUTORIAL_TYPE: "TUTORIAL",
    HYPERTOOL_TYPE: "HYPERTOOL",
    HYPERTOOL_ICON: "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/refs/heads/main/app/icons/hypertool.png",
    PIPELINE_ICON: "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/refs/heads/main/app/icons/diagram.png",
  },

  members: {
    __annotationsInitData: null,

    __applyMode: function(mode) {
      if (mode === "guided") {
        this.setMode("app");
      }
    },

    getAnnotationsInitData: function() {
      return this.__annotationsInitData;
    },

    nullAnnotationsInitData: function() {
      this.__annotationsInitData = null;
    },

    addAnnotation: function(annotation) {
      this.getAnnotations()[annotation.getId()] = annotation;
    },

    removeAnnotation: function(annotationId) {
      if (annotationId in this.getAnnotations()) {
        delete this.getAnnotations()[annotationId];
      }
    },

    removeNode: function(nodeId) {
      // remove it from slideshow
      this.getSlideshow().removeNode(nodeId);
    },

    serialize: function() {
      const currentStudy = osparc.store.Store.getInstance().getCurrentStudy();
      let jsonObject = {};
      jsonObject["workbench"] = currentStudy ? currentStudy.getWorkbench().serializeUI() : this.getWorkbench();
      jsonObject["slideshow"] = this.getSlideshow().serialize();
      jsonObject["currentNodeId"] = this.getCurrentNodeId() || "";
      jsonObject["mode"] = this.getMode();
      const annotations = this.getAnnotations();
      if (Object.keys(annotations).length) {
        jsonObject["annotations"] = {};
        Object.keys(annotations).forEach(annotationId => {
          jsonObject["annotations"][annotationId] = annotations[annotationId].serialize();
        });
      }
      return jsonObject;
    }
  }
});
