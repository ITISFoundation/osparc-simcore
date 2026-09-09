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
      slideshow: new osparc.data.model.Slideshow(studyDataUI && studyDataUI.slideshow ? studyDataUI.slideshow : this.getSlideshow()),
      currentNodeId: studyDataUI && studyDataUI.currentNodeId ? studyDataUI.currentNodeId : this.initCurrentNodeId(),
      mode: studyDataUI && studyDataUI.mode ? studyDataUI.mode : this.initMode(),
      annotations: {},
    });

    if (studyDataUI["annotations"]) {
      Object.entries(studyDataUI["annotations"]).forEach(([annotationId, annotationData]) => {
        this.addAnnotation(annotationData, annotationId);
      });
    }

    this.getSlideshow().addListener("changeSlideshow", () => {
      this.fireDataEvent("projectDocumentChanged", {
        "op": "replace",
        "path": "/ui/slideshow",
        "value": this.getSlideshow().serialize(),
        "osparc-resource": "study-ui",
      });
    }, this);
  },

  properties: {
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
    "annotationAdded": "qx.event.type.Data",
    "annotationRemoved": "qx.event.type.Data",
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

    addAnnotation: function(annotationData, annotationId) {
      const annotation = new osparc.workbench.Annotation(annotationData, annotationId);
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
      return annotation;
    },

    removeAnnotation: function(annotationId) {
      if (annotationId in this.getAnnotations()) {
        const annotation = this.getAnnotations()[annotationId]
        this.fireDataEvent("projectDocumentChanged", {
          "op": "remove",
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

    updateUiFromPatches: function(uiPatches) {
      uiPatches.forEach(patch => {
        const path = patch.path;
        if (path.startsWith("/ui/annotations")) {
          this.__updateAnnotationFromPatch(patch);
        }
      });
    },

    __updateAnnotationFromPatch: function(patch) {
      const op = patch.op;
      const path = patch.path;
      const value = patch.value;
      let annotationId = path.split("/")[3];
      switch (op) {
        case "add": {
          const annotation = this.addAnnotation(value, annotationId);
          this.fireDataEvent("annotationAdded", annotation);
          break;
        }
        case "remove":
          this.removeAnnotation(annotationId);
          this.fireDataEvent("annotationRemoved", annotationId);
          break;
        case "replace":
          if (annotationId && annotationId in this.getAnnotations()) {
            const annotation = this.getAnnotations()[annotationId];
            if (annotation) {
              if (path.includes("/color")) {
                annotation.setColor(value);
              } else if (path.includes("/attributes")) {
                this.__updateAnnotationAttributesFromPatch(annotation, path, value);
              }
            }
          } else if (value && Object.keys(value).length) {
            // the first (add) annotation will fall here
            annotationId = Object.keys(value)[0];
            const annotationData = Object.values(value)[0];
            const annotation = this.addAnnotation(annotationData, annotationId);
            this.fireDataEvent("annotationAdded", annotation);
          } else if (Object.keys(this.getAnnotations()).length === 1) {
            // the last (remove) annotation will fall here
            const currentIds = Object.keys(this.getAnnotations());
            annotationId = currentIds[0];
            this.removeAnnotation(annotationId);
            this.fireDataEvent("annotationRemoved", annotationId);
          }
          break;
      }
    },

    __updateAnnotationAttributesFromPatch: function(annotation, path, value) {
      if (annotation) {
        const attribute = path.split("/")[5];
        switch (attribute) {
          case "x": {
            const newPos = annotation.getPosition();
            newPos.x = value;
            annotation.setPosition(newPos.x, newPos.y);
            break;
          }
          case "y": {
            const newPos = annotation.getPosition();
            newPos.y = value;
            annotation.setPosition(newPos.x, newPos.y);
            break;
          }
          case "fontSize":
            annotation.setFontSize(value);
            break;
          case "text":
            annotation.setText(value);
            break;
        }
      }
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
      let jsonObject = {};
      jsonObject["slideshow"] = this.getSlideshow().serialize();
      jsonObject["currentNodeId"] = this.getCurrentNodeId() || "";
      jsonObject["mode"] = this.getMode();
      jsonObject["annotations"] = null;
      const annotations = this.getAnnotations();
      if (Object.keys(annotations).length) {
        jsonObject["annotations"] = {};
        Object.keys(annotations).forEach(annotationId => {
          jsonObject["annotations"][annotationId] = annotations[annotationId].serialize();
        });
      }

      // return a deep clone of the object to avoid modifications to the original object
      return osparc.utils.Utils.deepCloneObject(jsonObject);
    }
  }
});
