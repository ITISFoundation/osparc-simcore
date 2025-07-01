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
 * @asset(svg/svg.foreignobject.js)
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

    /* ANNOTATIONS */

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
      const defaultFont = osparc.utils.Utils.getDefaultFont();
      const text = draw.text(label)
        .font({
          fill: color,
          size: (fontSize ? fontSize : defaultFont["size"]) + "px",
          family: defaultFont["family"]
        })
        .style({
          cursor: "pointer"
        })
        .move(x, y);
      text.back();
      return text;
    },

    drawAnnotationNote: function(draw, x, y, recipientName, note) {
      const lines = note.split("\n");
      const width = 200;
      const minHeight = 120;
      const titleHeight = 26;
      const padding = 5;
      const nLines = lines.length;
      const height = Math.max(minHeight, titleHeight + nLines*18);
      const trianSize = 25;
      const yellow = "#FFFF01"; // do not make it pure yellow, svg will change the hex value to a "yellow" string
      const orange = "#FFA500";
      x = parseInt(x);
      y = parseInt(y);

      const gNote = draw.nested().move(x, y);
      const rect = gNote.rect(width, height)
        .fill(yellow)
        .style({
          cursor: "pointer"
        });
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
        .move(width-trianSize, height-trianSize);
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
        .move(width-trianSize, height-trianSize);
      trianTransparent.back();
      colorManager.addListener("changeTheme", () => {
        const bgColor = colorManager.resolve("background-main");
        trianTransparent.fill(bgColor);
      }, this);
      gNote.add(trianTransparent);

      const separator = gNote.line(0, 0, width-2*padding, 0)
        .stroke({
          width: 2,
          color: orange
        })
        .move(padding, titleHeight);
      separator.back();
      gNote.add(separator);

      const defaultFont = osparc.utils.Utils.getDefaultFont();
      const title = gNote.text(recipientName)
        .font({
          fill: "#000000",
          size: (defaultFont["size"]+1) + "px",
          family: defaultFont["family"]
        })
        .move(padding, padding);
      title.back();
      gNote.add(title);

      // size and id are not relevant
      const fobj = gNote.foreignObject(100, 100).attr({id: "fobj"});
      fobj.appendChild("div", {
        id: "mydiv",
        innerText: note
      });
      fobj
        .attr({
          width: width-2*padding,
          height: height-titleHeight-4
        })
        .move(padding, padding+titleHeight);
      const textChild = fobj.getChild(0);
      textChild.style.overflow = "auto";
      textChild.style.overflowWrap = "anywhere";
      textChild.style.fontFamily = defaultFont["family"];
      textChild.style.fontSize = defaultFont["size"] + "px";
      gNote.textChild = textChild;
      gNote.add(fobj);

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

    drawAnnotationConversation: function(draw, x = 50, y = 50, title = "Conversation") {
      const color = qx.theme.manager.Color.getInstance().getTheme().colors["text"];
      const bubbleWidth = 150;
      const bubbleHeight = 30;
      const padding = 6;

      // Group to keep all elements together
      const bubble = draw.group();
      bubble.move(x, y);

      // Rounded rectangle as the base
      const rect = draw.rect(bubbleWidth, bubbleHeight)
        .radius(4)
        .fill("none")
        .stroke({
          color,
          width: 1.5,
        });
      bubble.add(rect);

      // Icon (simple speech bubble using path or text)
      const iconSize = 16;
      const icon = draw.text('💬')
        .font({
          size: iconSize
        })
        .move(padding, (bubbleHeight - iconSize) / 2)
        .attr({
          cursor: "pointer"
        });
      bubble.add(icon);

      // Title text
      const titleFontSize = 12;
      const defaultFont = osparc.utils.Utils.getDefaultFont();
      const label = draw.text(title)
        .font({
          fill: color,
          size: titleFontSize,
          family: defaultFont["family"],
          anchor: 'start'
        })
        .move(padding + iconSize + 8, ((bubbleHeight - titleFontSize) / 2) - 3);
      bubble.add(label);

      // Compute available width for text
      const availableWidth = bubbleWidth - padding * 2 - iconSize - 8;

      // Helper: truncate text with ellipsis
      const fitTextWithEllipsis = (fullText, maxWidth) => {
        let text = fullText;
        label.text(text);
        if (label.bbox().width <= maxWidth) {
          return text
        };

        const ellipsis = '…';
        let low = 0;
        let high = text.length;
        // Binary search for the max fitting length
        while (low < high) {
          const mid = Math.floor((low + high) / 2);
          label.text(text.slice(0, mid) + ellipsis);
          if (label.bbox().width <= maxWidth) {
            low = mid + 1;
          } else {
            high = mid;
          }
        }
        return text.slice(0, low - 1) + ellipsis;
      }

      // Truncate if needed
      const fittedText = fitTextWithEllipsis(title, availableWidth);
      label.text(fittedText);

      // Move label to proper position
      label.move(padding + iconSize + 8, ((bubbleHeight - titleFontSize) / 2) - 3);

      bubble.back();

      return bubble;
    },

    updateText: function(representation, label) {
      if (representation.type === "text") {
        representation.text(label);
      } else if (representation.type === "svg") {
        // nested
        representation["textChild"].innerText = label;
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

    /* / ANNOTATIONS */

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
        const svgAndPlugins = [
          "svg/svg.js",
          "svg/svg.draggable.js",
          "svg/svg.path.js",
          "svg/svg.foreignobject.js"
        ];
        const dynLoader = new qx.util.DynamicScriptLoader(svgAndPlugins);
        dynLoader.addListenerOnce("ready", () => {
          console.log("svgAndPlugins loaded");
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
