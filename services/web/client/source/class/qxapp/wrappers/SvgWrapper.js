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

      dynLoader.addListenerOnce("ready", function(e) {
        console.log(svgPath + " loaded");
        this.setLibReady(true);
        this.fireDataEvent("SvgLibReady", true);
      }, this);

      dynLoader.addListener("failed", function(e) {
        let data = e.getData();
        console.log("failed to load " + data.script);
        this.fireDataEvent("SvgLibReady", false);
      }, this);

      dynLoader.start();
    },

    createEmptyCanvas: function(id) {
      return SVG(id);
    },

    drawCurve: function(draw, controls) {
      const linkColor = qxapp.theme.Color.colors["workbench-link-active"];

      let path = draw.path()
        .M(controls[0].x, controls[0].y)
        .C(controls[1], controls[2], controls[3])
        .fill("none")
        .stroke({
          width: 3,
          color: linkColor
        });

      const portSphereDiameter = 4;
      let marker1 = draw.marker(portSphereDiameter, portSphereDiameter, function(add) {
        add.circle(portSphereDiameter)
          .fill(linkColor);
      });
      path.marker("start", marker1);

      const arrowSize = 4;
      let marker2 = draw.marker(arrowSize, arrowSize, function(add) {
        add.path("M 0 0 V 4 L 2 2 Z")
          .fill(linkColor)
          .size(arrowSize, arrowSize);
      });
      path.marker("end", marker2);

      path.markers = [marker1, marker2];

      return path;
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
    },

    removeCurve: function(curve) {
      if (curve.type === "path") {
        curve.remove();
      }
    },

    updateColor: function(curve, color) {
      if (curve.type === "path") {
        curve.attr({
          stroke: color
        });
        if (curve.markers) {
          curve.markers.forEach(markerDiv => {
            markerDiv.node.childNodes.forEach(node => {
              node.setAttribute("fill", color);
            });
          });
        }
      }
    }
  }
});
