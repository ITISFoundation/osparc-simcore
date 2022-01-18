/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global SVG */
/* eslint new-cap: [2, {capIsNewExceptions: ["SVG", "M", "C"]}] */

/**
 * @asset(svg/svg.*js)
 * @ignore(SVG)
 */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/svgdotjs/svg.js' target='_blank'>SVG</a>
 */

qx.Class.define("osparc.wrapper.Svg", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    }
  },

  statics: {
    NAME: "svg.js",
    VERSION: "2.7.1",
    URL: "https://github.com/svgdotjs/svg.js",

    curateCurveControls: function(controls) {
      [
        controls[0],
        controls[1],
        controls[2],
        controls[3]
      ].forEach(control => {
        if (Number.isNaN(control.x)) {
          control.x = 0;
        }
        if (Number.isNaN(control.y)) {
          control.y = 0;
        }
      });
    },

    drawCurve: function(draw, controls, dashed) {
      const edgeWidth = 3;
      const arrowSize = 4;
      const edgeColor = qx.theme.manager.Color.getInstance().getTheme().colors["workbench-edge-comp-active"];

      osparc.wrapper.Svg.curateCurveControls(controls);

      const widerCurve = draw.path()
        .M(controls[0].x, controls[0].y)
        .C(controls[1], controls[2], controls[3])
        .style({
          cursor: "pointer"
        })
        .opacity(0)
        .stroke({
          width: edgeWidth*4
        });

      const curve = draw.path()
        .M(controls[0].x, controls[0].y)
        .C(controls[1], controls[2], controls[3])
        .fill("none")
        .style({
          cursor: "pointer"
        })
        .stroke({
          width: edgeWidth,
          color: edgeColor,
          dasharray: dashed ? 5 : 0
        });
      curve.widerCurve = widerCurve;

      const portArrow = draw.marker(arrowSize, arrowSize, add => {
        add.path("M 0 0 V 4 L 2 2 Z")
          .fill(edgeColor)
          .size(arrowSize, arrowSize);
      });
      curve.marker("end", portArrow);
      curve.markers = [portArrow];

      return curve;
    },

    updateCurve: function(curve, controls) {
      if (curve.type === "path") {
        let mSegment = curve.getSegment(0);
        mSegment.coords = [controls[0].x, controls[0].y];
        let cSegment = curve.getSegment(1);
        cSegment.coords = [controls[1].x, controls[1].y, controls[2].x, controls[2].y, controls[3].x, controls[3].y];

        if (curve.widerCurve) {
          curve.widerCurve.replaceSegment(0, mSegment);
          curve.widerCurve.replaceSegment(1, cSegment);
        }
        curve.replaceSegment(0, mSegment);
        curve.replaceSegment(1, cSegment);
      }
    },

    removeCurve: function(curve) {
      if (curve.type === "path") {
        if (curve.widerCurve) {
          curve.widerCurve.remove();
        }
        curve.remove();
      }
    },

    drawDashedRect: function(draw, width, height, x, y) {
      const edgeColor = qx.theme.manager.Color.getInstance().getTheme().colors["workbench-edge-comp-active"];
      const rect = draw.rect(width, height)
        .fill("none")
        .stroke({
          // width: 5,
          color: edgeColor,
          dasharray: "4, 4"
        })
        .move(x, y);
      return rect;
    },

    drawFilledRect: function(draw, width, height, x, y) {
      const fillColor = qx.theme.manager.Color.getInstance().resolve("background-main-lighter");
      const edgeColor = qx.theme.manager.Color.getInstance().resolve("background-main-lighter+");
      const rect = draw.rect(width, height)
        .fill(fillColor)
        .stroke({
          width: 1,
          color: edgeColor
        })
        .move(x, y);
      rect.back();
      return rect;
    },

    drawNodeUI: function(draw, width, height, radius, x, y) {
      const nodeUIColor = qx.theme.manager.Color.getInstance().getTheme().colors["window-border"];
      const rect = draw.rect(width, height)
        .fill(nodeUIColor)
        .stroke({
          width: 0.2,
          color: "black"
        })
        .move(x, y)
        .attr({
          rx: radius,
          ry: radius
        });
      return rect;
    },

    updateRect: function(rect, w, h, x, y) {
      rect.width(w);
      rect.height(h);
      rect.move(x, y);
    },

    updateRectPos: function(rect, x, y) {
      rect.move(x, y);
    },

    removeRect: function(rect) {
      rect.remove();
    },

    updateCurveDashes: function(curve, dashed) {
      curve.attr({
        "stroke-dasharray": dashed ? 5 : 0
      });
    },

    updateCurveColor: function(curve, color) {
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
    },

    drawPolygon: function(draw, controls) {
      const polygon = draw.polygon(controls.join())
        .fill("none")
        .stroke({
          width: 0
        })
        .move(0, 0);
      return polygon;
    },

    updatePolygonColor: function(polygon, color) {
      polygon.fill(color);
    },

    drawPolyline: function(draw, controls) {
      const polyline = draw.polyline(controls.join())
        .fill("none")
        .stroke({
          color: "#BFBFBF",
          width: 1
        });
      return polyline;
    },

    updateStrokeColor: function(polyline, color) {
      polyline.stroke({
        color: color
      });
    },

    updateNodeUI: function(nodeUI, x, y) {
      nodeUI.move(x, y);
    },

    removeNodeUI: function(nodeUI) {
      nodeUI.remove();
    },

    drawLine: function(draw, controls) {
      const line = draw.line(controls.join())
        .fill("none")
        .stroke({
          color: "#BFBFBF",
          width: 1
        })
        .move(0, 0);
      return line;
    },

    drawPath: function(draw, controls) {
      const polygon = draw.path(controls)
        .fill("none")
        .stroke({
          width: 0
        })
        .move(0, 0);
      return polygon;
    }
  },

  members: {
    init: function() {
      return new Promise((resolve, reject) => {
        if (this.getLibReady()) {
          resolve();
          return;
        }

        // initialize the script loading
        const svgPath = "svg/svg.js";
        const svgPathPath = "svg/svg.path.js";
        const dynLoader = new qx.util.DynamicScriptLoader([
          svgPath,
          svgPathPath
        ]);

        dynLoader.addListenerOnce("ready", () => {
          console.log(svgPath + " loaded");
          this.setLibReady(true);
          resolve();
        }, this);

        dynLoader.addListener("failed", e => {
          const data = e.getData();
          console.error("failed to load " + data.script);
          reject(data);
        }, this);

        dynLoader.start();
      });
    },

    createEmptyCanvas: function(element) {
      return SVG(element);
    }
  }
});
