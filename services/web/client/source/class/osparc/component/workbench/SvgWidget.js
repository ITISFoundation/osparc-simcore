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

/**
 * Widget that provides a SVG painting layer that goes on top of the WorkbenchUI.
 *
 * In this layer arrows that represent internode connections are drawn.
 *
 * Also provides access to the SVG Wrapper.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let svgWidget = new osparc.component.workbench.SvgWidget("SvgWidget_(Purporse)");
 *   this.getRoot().add(svgWidget);
 * </pre>
 */

qx.Class.define("osparc.component.workbench.SvgWidget", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base();
    this.addListenerOnce("appear", () => {
      const el = this.getContentElement().getDomElement();
      const svgWrapper = osparc.wrapper.Svg.getInstance();
      svgWrapper.init()
        .then(() => {
          if (this.__canvas === null) {
            this.__canvas = svgWrapper.createEmptyCanvas(el);
            this.setReady(true);
            this.fireDataEvent("SvgWidgetReady", true);
          }
        }, this);
    });
  },

  properties: {
    ready: {
      check: "Boolean",
      init: false
    }
  },

  events: {
    "SvgWidgetReady": "qx.event.type.Data"
  },

  statics: {
    getCurveControls: function(x1, y1, x2, y2, offset = 100) {
      return [{
        x: x1,
        y: y1
      }, {
        x: x1+offset,
        y: y1
      }, {
        x: x2-offset,
        y: y2
      }, {
        x: x2,
        y: y2
      }];
    },

    updateCurve: function(curve, x1, y1, x2, y2) {
      const controls = osparc.component.workbench.SvgWidget.getCurveControls(x1, y1, x2, y2);
      osparc.wrapper.Svg.updateCurve(curve, controls);
    },

    removeCurve: function(curve) {
      osparc.wrapper.Svg.removeCurve(curve);
    },

    updateRect: function(rect, x, y) {
      osparc.wrapper.Svg.updateRect(rect, x, y);
    },

    removeRect: function(rect) {
      osparc.wrapper.Svg.removeRect(rect);
    },

    updateCurveDashes: function(curve, dashed = false) {
      osparc.wrapper.Svg.updateCurveDashes(curve, dashed);
    },

    updateCurveColor: function(curve, color) {
      osparc.wrapper.Svg.updateCurveColor(curve, color);
    }
  },

  members: {
    __canvas: null,

    drawCurve: function(x1, y1, x2, y2, dashed = false) {
      const controls = this.self().getCurveControls(x1, y1, x2, y2);
      return osparc.wrapper.Svg.drawCurve(this.__canvas, controls, dashed);
    },

    drawDashedRect: function(width, height, x = 0, y = 0) {
      return osparc.wrapper.Svg.drawDashedRect(this.__canvas, width, height, x, y);
    }
  }
});
