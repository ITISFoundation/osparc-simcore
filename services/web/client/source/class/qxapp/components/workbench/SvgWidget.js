const LINKS_LAYER_ID = "drawing";

qx.Class.define("qxapp.components.workbench.SvgWidget", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base();

    this.addListenerOnce("appear", function() {
      this.__svgWrapper = new qxapp.wrappers.SvgWrapper();
      this.__svgWrapper.addListener(("SvgLibReady"), function(e) {
        let ready = e.getData();
        if (ready) {
          let svgPlaceholder = qx.dom.Element.create("div");
          qx.bom.element.Attribute.set(svgPlaceholder, "id", LINKS_LAYER_ID);
          qx.bom.element.Style.set(svgPlaceholder, "z-index", 12);
          qx.bom.element.Style.set(svgPlaceholder, "width", "100%");
          qx.bom.element.Style.set(svgPlaceholder, "height", "100%");
          this.getContentElement().getDomElement()
            .appendChild(svgPlaceholder);
          this.__linksCanvas = this.__svgWrapper.createEmptyCanvas(LINKS_LAYER_ID);
          this.fireDataEvent("SvgWidgetReady", true);
        } else {
          console.log("svg.js was not loaded");
        }
      }, this);

      this.__svgWrapper.init();
    }, this);
  },

  events: {
    "SvgWidgetReady": "qx.event.type.Data"
  },

  members: {
    __svgWrapper: null,
    __linksCanvas: null,

    __getControls: function(x1, y1, x2, y2) {
      const offset = 50;
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
    }
  }
});
