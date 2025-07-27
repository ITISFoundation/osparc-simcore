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

    updateUiFromDiff: function(uiDiff) {
      if (uiDiff["workbench"]) {
        const currentStudy = osparc.store.Store.getInstance().getCurrentStudy();
        if (currentStudy) {
          Object.keys(uiDiff["workbench"]).forEach(nodeId => {
            const node = currentStudy.getWorkbench().getNode(nodeId);
            if ("position" in uiDiff["workbench"][nodeId]) {
              const positionDiff = uiDiff["workbench"][nodeId]["position"];
              this.__updateNodePositionFromDiff(node, positionDiff);
            }
            if ("marker" in uiDiff["workbench"][nodeId]) {
              const markerDiff = uiDiff["workbench"][nodeId]["marker"];
              this.__updateNodeMarkerFromDiff(node, markerDiff);
            }
          });
        }
      }
      if (uiDiff["annotations"]) {
        const annotationsData = uiDiff["annotations"];
        this.__updateAnnotationsFromDiff(annotationsData);
      }
    },

    __updateNodePositionFromDiff: function(node, positionDiff) {
      if (node) {
        const newPos = node.getPosition();
        if ("x" in positionDiff) {
          newPos.x = positionDiff["x"][1];
        }
        if ("y" in positionDiff) {
          newPos.y = positionDiff["y"][1];
        }
        node.setPosition(newPos);
      }
    },

    __updateNodeMarkerFromDiff: function(node, markerDiff) {
      if (node) {
        if (markerDiff instanceof Array) {
          if (markerDiff.length === 1) {
            // it was added
            node.addMarker(markerDiff[0]);
          } else if (markerDiff.length === 2 && markerDiff[1] === null) {
            // it was removed
            node.setMarker(null);
          }
        } else if ("color" in markerDiff && markerDiff["color"] instanceof Array) {
          // it was updated
          const newColor = markerDiff["color"][1];
          node.getMarker().setColor(newColor);
        }
      }
    },

    __updateAnnotationPositionFromDiff: function(annotation, positionDiff) {
      if (annotation) {
        const newPos = annotation.getPosition();
        if ("x" in positionDiff) {
          newPos.x = positionDiff["x"][1];
        }
        if ("y" in positionDiff) {
          newPos.y = positionDiff["y"][1];
        }
        annotation.setPosition(newPos.x, newPos.y);
      }
    },

    __updateAnnotationsFromDiff: function(annotationsData) {
      // check if annotation data is an object or an array
      const annotations = this.getAnnotations();
      Object.entries(annotationsData).forEach(([annotationId, annotationDiff]) => {
        if (annotationDiff instanceof Array) {
          if (annotationDiff.length === 1) {
            // it was added
            const annotation = this.addAnnotation(annotationDiff[0], annotationId);
            this.fireDataEvent("annotationAdded", annotation);
          } else if (annotationDiff.length === 3 && annotationDiff[1] === 0) {
            // it was removed
            this.removeAnnotation(annotationId);
            this.fireDataEvent("annotationRemoved", annotationId);
          }
        } else if (annotationDiff instanceof Object) {
          // it was updated
          if (annotationId in annotations) {
            const annotation = annotations[annotationId];
            if ("attributes" in annotationDiff) {
              this.__updateAnnotationPositionFromDiff(annotation, annotationDiff["attributes"]);
            }
            if ("color" in annotationDiff) {
              annotation.setColor(annotationDiff["color"][1]);
            }
          } else {
            console.warn(`Annotation with id ${annotationId} not found`);
          }
        }
      });
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
      jsonObject["annotations"] = null;
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
