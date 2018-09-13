qx.Class.define("qxapp.components.workbench.SvgWidget", {
  extend: qx.ui.core.Widget,

  construct: function(svgLayerId) {
    this.base();
    this.addListenerOnce("appear", () => {
      let el = this.getContentElement().getDomElement();
      qx.bom.element.Attribute.set(el, "id", svgLayerId);
      this.__svgWrapper = new qxapp.wrappers.SvgWrapper();
      this.__svgWrapper.addListener(("SvgLibReady"), () => {
        this.__linksCanvas = this.__svgWrapper.createEmptyCanvas(svgLayerId);
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
    __linksCanvas: null,

    __getControls: function(x1, y1, x2, y2) {
      const offset = 60;
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
      return this.__svgWrapper.drawCurve(this.__linksCanvas, controls);
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
