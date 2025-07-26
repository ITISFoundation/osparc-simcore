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
    });

    if ("annotations" in studyDataUI) {
      Object.entries(studyDataUI["annotations"]).forEach(([annotationId, annotationData]) => {
        const annotation = new osparc.workbench.Annotation(annotationData, annotationId);
        this.addAnnotation(annotation);
      });
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
  },

  events: {
    "projectDocumentChanged": "qx.event.type.Data",
  },

  statics: {
    TEMPLATE_TYPE: "TEMPLATE",
    TUTORIAL_TYPE: "TUTORIAL",
    HYPERTOOL_TYPE: "HYPERTOOL",
    HYPERTOOL_ICON: "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/refs/heads/main/app/icons/hypertool.png",
    PIPELINE_ICON: "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/refs/heads/main/app/icons/diagram.png",

    ListenChangesProps: [
      // "workbench", it's handled by osparc.data.model.Workbench
      "slideshow",
      "currentNodeId", // eventually don't patch it, it is personal, only the last closing sets it
      "mode", // eventually don't patch it, it is personal, only the last closing sets it
      "annotations", // TODO
    ],
  },

  members: {
    __applyMode: function(mode) {
      if (mode === "guided") {
        this.setMode("app");
      }
    },

    addAnnotation: function(annotation) {
      this.getAnnotations()[annotation.getId()] = annotation;
      this.fireDataEvent("projectDocumentChanged", {
        "op": "add",
        "path": `/ui/annotations/${annotation.getId()}`,
        "value": annotation.serialize(),
        "osparc-resource": "study-ui",
      });
      annotation.addListener("annotationChanged", () => {
        this.fireDataEvent("projectDocumentChanged", {
          "op": "replace",
          "path": `/ui/annotations/${annotation.getId()}`,
          "value": annotation.serialize(),
          "osparc-resource": "study-ui",
        });
      }, this);
    },

    removeAnnotation: function(annotationId) {
      if (annotationId in this.getAnnotations()) {
        const annotation = this.getAnnotations()[annotationId]
        this.fireDataEvent("projectDocumentChanged", {
          "op": "delete",
          "path": `/ui/annotations/${annotation.getId()}`,
          "osparc-resource": "study-ui",
        });
        delete this.getAnnotations()[annotationId];
      }
    },

    removeNode: function(nodeId) {
      // remove it from slideshow
      this.getSlideshow().removeNode(nodeId);
    },

    listenToChanges: function() {
      const propertyKeys = Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.StudyUI));
      this.self().ListenChangesProps.forEach(key => {
        switch (key) {
          default:
            if (propertyKeys.includes(key)) {
              this.addListener(`change${qx.lang.String.firstUp(key)}`, () => {
                const data = this.serialize();
                this.fireDataEvent("projectDocumentChanged", {
                  "op": "replace",
                  "path": `/ui/${key}`,
                  "value": data,
                  "osparc-resource": "study-ui",
                });
              }, this);
            } else {
              console.error(`Property "${key}" is not a valid property of osparc.data.model.StudyUI`);
            }
            break;
        }
      });
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
