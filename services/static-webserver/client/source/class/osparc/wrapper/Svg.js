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
 * @asset(svg/svg.js)
 * @asset(svg/svg.path.js)
 * @asset(svg/svg.draggable.js)
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

    NOTE_GROUP: {
      RECT: {
        IDX: 0
      },
      TRIAN_1: {
        IDX: 1
      },
      TRIAN_2: {
        IDX: 2
      },
      SEPARATOR: {
        IDX: 3
      },
      DETINATARY: {
        IDX: 4
      },
      NOTE: {
        IDX: 5
      }
    },

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

    getRectAttributes: function(rect) {
      const rectAttrs = rect.node.attributes;
      return {
        x: rectAttrs.x.value,
        y: rectAttrs.y.value,
        width: rectAttrs.width ? rectAttrs.width.value : null,
        height: rectAttrs.height ? rectAttrs.height.value : null
      };
    },

    drawAnnotationText: function(draw, x, y, label, color, fontSize) {
      const text = draw.text(label)
        .font({
          fill: color,
          size: (fontSize ? fontSize : 13) + "px",
          family: "Roboto"
        })
        .style({
          cursor: "pointer"
        })
        .move(x, y);
      text.back();
      return text;
    },

    drawAnnotationNote: function(draw, x, y, destinatary, note) {
      const gNote = draw.nested();
      const width = 150;
      const lines = note.split("\n").length;
      const height = Math.max(120, lines*20);
      const trianSize = 25;
      const yellow = "#FFFF01"; // do not make it pure yellow, svg will change the hex value to a "yellow" string
      const orange = "#FFA500";
      x = parseInt(x);
      y = parseInt(y);

      const rect = gNote.rect(width, height)
        .fill(yellow)
        .style({
          cursor: "pointer"
        })
        .move(x, y);
      rect.back();
      gNote.add(rect);

      const trianOrangeCtrls = [
        [width-trianSize, height-trianSize],
        [width-trianSize, height],
        [width, height-trianSize]
      ];
      const trianOrange = gNote.polygon(trianOrangeCtrls.join())
        .fill(orange)
        .style({
          cursor: "pointer"
        })
        .move(x+width-trianSize, y+height-trianSize);
      trianOrange.back();
      gNote.add(trianOrange);

      const trianTransparentCtrls = [
        [width-trianSize, height],
        [width, height],
        [width, height-trianSize]
      ];
      const colorManager = qx.theme.manager.Color.getInstance();
      const trianTransparent = gNote.polygon(trianTransparentCtrls.join())
        .fill(colorManager.resolve("background-main"))
        .style({
          cursor: "pointer"
        })
        .move(x+width-trianSize, y+height-trianSize);
      trianTransparent.back();
      colorManager.addListener("changeTheme", () => {
        const bgColor = colorManager.resolve("background-main");
        trianTransparent.fill(bgColor);
      }, this);
      gNote.add(trianTransparent);

      const line = gNote.line(0, 0, width-8, 0)
        .stroke({
          width: 2,
          color: orange
        })
        .move(x+4, y+24);
      line.back();
      gNote.add(line);

      const offsetX = 6;
      const offsetY = 4;
      const title = gNote.text(destinatary)
        .font({
          fill: "#000000",
          size: "14px",
          family: "Roboto"
        })
        .move(x+offsetX, y+offsetY);
      title.back();
      gNote.add(title);

      const text = gNote.text(note)
        .font({
          fill: "#000000",
          size: "13px",
          family: "Roboto"
        })
        .move(x+offsetX, y+offsetY+24);
      text.back();
      gNote.text = text;
      gNote.add(text);

      return gNote;
    },

    drawAnnotationRect: function(draw, width, height, x, y, color) {
      const rect = draw.rect(width, height)
        .fill("none")
        .stroke({
          width: 2,
          color
        })
        .style({
          cursor: "pointer"
        })
        .move(x, y);
      rect.back();
      return rect;
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
      const fillColor = qx.theme.manager.Color.getInstance().resolve("background-main-1");
      const edgeColor = qx.theme.manager.Color.getInstance().resolve("background-main-2");
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
      const nodeUIColor = qx.theme.manager.Color.getInstance().resolve("background-main-3");
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

    updateItemPos: function(item, x, y) {
      item.move(x, y);
    },

    updateItemColor: function(item, color) {
      item.stroke({
        color: color
      });
    },

    removeItem: function(item) {
      item.remove();
    },

    updateText: function(representation, label) {
      if (representation.type === "text") {
        representation.text(label);
      } else if (representation.type === "svg") {
        // nested
        representation["text"].text(label);
      }
    },

    updateTextColor: function(text, color) {
      text.font({
        fill: color
      });
    },

    updateTextSize: function(text, size) {
      text.font({
        size: size + "px"
      });
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
    },

    makeDraggable: function(item, draggable = true) {
      item.style({
        cursor: "move"
      });
      item.draggable(draggable);
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
        const svgDraggablePath = "svg/svg.draggable.js";
        const svgPathPath = "svg/svg.path.js";
        const dynLoader = new qx.util.DynamicScriptLoader([
          svgPath,
          svgDraggablePath,
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
