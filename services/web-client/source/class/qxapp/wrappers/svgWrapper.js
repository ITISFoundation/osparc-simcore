/**
 * @asset(workbench/svg.*js)
 * @ignore(SVG)
 */

/* global SVG */
/* eslint new-cap: [2, {capIsNewExceptions: ["SVG", "M", "C"]}] */

qx.Class.define("qxapp.wrappers.SvgWrapper", {
  extend: qx.core.Object,

  construct: function() {
  },

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    }
  },

  events: {
    "SvgLibReady": "qx.event.type.Data"
  },

  members: {
    init: function() {
      // initialize the script loading
      let svgPath = "workbench/svg.js";
      let svgPathPath = "workbench/svg.path.js";
      let dynLoader = new qx.util.DynamicScriptLoader([
        svgPath,
        svgPathPath
      ]);

      let scope = this;
      dynLoader.addListenerOnce("ready", function(e) {
        console.log(svgPath + " loaded");
        scope.setLibReady(true);
        scope.fireDataEvent("SvgLibReady", true);
      }, scope);

      dynLoader.addListener("failed", function(e) {
        let data = e.getData();
        console.log("failed to load " + data.script);
        scope.fireDataEvent("SvgLibReady", false);
      }, scope);

      dynLoader.start();
    },

    createEmptyCanvas: function(id) {
      return SVG(id);
    },

    drawCurve: function(draw, controls) {
      return draw.path()
        .M(controls[0].x, controls[0].y)
        .C(controls[1], controls[2], controls[3])
        .fill("none")
        .stroke({
          width: 3,
          color: "#00F"
        });
    },

    updateCurve: function(curve, controls) {
      if (curve.type === "path") {
        let mSegment = curve.getSegment(0);
        mSegment.coords = [controls[0].x, controls[0].y];
        curve.replaceSegment(0, mSegment);

        let cSegment = curve.getSegment(1);
        cSegment.coords = [controls[1].x, controls[1].y, controls[2].x, controls[2].y, controls[3].x, controls[3].y];
        curve.replaceSegment(1, cSegment);
      }
    }
  }
});
