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

  /**
    * @param svgLayerId {String} Element id to set it as dom attribute
  */
  construct: function(svgLayerId) {
    this.base();
    this.addListenerOnce("appear", () => {
      let el = this.getContentElement().getDomElement();
      qx.bom.element.Attribute.set(el, "id", svgLayerId);
      const svgWrapper = new osparc.wrapper.Svg();
      svgWrapper.addListener("svgLibReady", () => {
        if (this.__canvas === null) {
          this.__canvas = svgWrapper.createEmptyCanvas(svgLayerId);
          this.setReady(true);
          this.fireDataEvent("SvgWidgetReady", true);
        }
      });
      svgWrapper.init();
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
    getCurveControls: function(x1, y1, x2, y2, offset = 60) {
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

    updateCurve: function(curve, x1, y1, x2, y2, dashed = false) {
      const controls = osparc.component.workbench.SvgWidget.getCurveControls(x1, y1, x2, y2);
      osparc.wrapper.Svg.updateCurve(curve, controls, dashed);
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

    drawDashedRect: function(width, height, x, y) {
      return osparc.wrapper.Svg.drawDashedRect(this.__canvas, width, height, x, y);
    }
  }
});
