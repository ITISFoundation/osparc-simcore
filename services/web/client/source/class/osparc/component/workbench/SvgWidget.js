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
 *   let svgWidget = new osparc.component.workbench.SvgWidget("SvgWidgetLayer");
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
      this.__svgWrapper = new osparc.wrapper.Svg();
      this.__svgWrapper.addListener(("svgLibReady"), () => {
        this.__edgesCanvas = this.__svgWrapper.createEmptyCanvas(svgLayerId);
        this.fireDataEvent("SvgWidgetReady", true);
      });
      this.__svgWrapper.init();
    });
  },

  events: {
    "SvgWidgetReady": "qx.event.type.Data"
  },

  members: {
    __svgWrapper: null,
    __edgesCanvas: null,

    __getControls: function(x1, y1, x2, y2, offset = 60) {
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

    drawCurve: function(x1, y1, x2, y2) {
      const controls = this.__getControls(x1, y1, x2, y2);
      return this.__svgWrapper.drawCurve(this.__edgesCanvas, controls);
    },

    updateCurve: function(curve, x1, y1, x2, y2) {
      const controls = this.__getControls(x1, y1, x2, y2);
      this.__svgWrapper.updateCurve(curve, controls);
    },

    removeCurve: function(curve) {
      this.__svgWrapper.removeCurve(curve);
    },

    updateColor: function(curve, color) {
      this.__svgWrapper.updateColor(curve, color);
    }
  }
});
